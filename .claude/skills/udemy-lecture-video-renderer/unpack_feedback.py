#!/usr/bin/env python3
"""Unpack a feedback bundle (JSON) into the markdown format the iteration loop consumes.

Input: a feedback-bundle-X.Y-<timestamp>.json file exported by the per-lecture
feedback HTML page.

Output:
  <course_root>/feedback/<date>/X.Y-video-generation-feedback-N.md
  <course_root>/feedback/<date>/X.Y-feedback-images-N/<image_files>...

The markdown format matches rounds 1-3 conventions (used through the lecture-2.1
polish loop): per-slide `# Slide N (Title)` headings with bullet-point feedback,
followed by image references for any attachments. The N suffix auto-increments
based on existing files in the target date directory.

Usage:
    python unpack_feedback.py path/to/feedback-bundle-2.2-2026-05-24T10-30-00.json
    python unpack_feedback.py path/to/bundle.json --course-root /custom/path
    python unpack_feedback.py path/to/bundle.json --date 2026-05-24
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import sys
from pathlib import Path


def _next_revision_number(date_dir: Path, lecture_id: str) -> int:
    """Find the lowest N such that X.Y-video-generation-feedback-N.md doesn't yet exist.

    Existing un-numbered file (X.Y-video-generation-feedback.md without -N) counts
    as N=1 for ordering purposes — so the next file we write is N=2.
    """
    if not date_dir.exists():
        return 1
    # If a no-suffix file exists, treat it as the implicit "round 1"
    base_path = date_dir / f"{lecture_id}-video-generation-feedback.md"
    n = 2 if base_path.exists() else 1
    while True:
        candidate = date_dir / f"{lecture_id}-video-generation-feedback-{n}.md"
        if not candidate.exists():
            return n
        n += 1


def _format_feedback_text_as_bullets(text: str) -> list[str]:
    """Convert raw user text into a list of bullets.

    Splits on blank lines into paragraphs; each paragraph becomes one bullet.
    If a paragraph already starts with "- " or "* ", treat each line as its
    own bullet (so users can author multi-bullet feedback inline).
    """
    text = text.strip()
    if not text:
        return []
    bullets: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        lines = para.split("\n")
        leads_with_bullet = any(line.lstrip().startswith(("- ", "* ")) for line in lines)
        if leads_with_bullet:
            for line in lines:
                s = line.strip()
                if not s:
                    continue
                if s.startswith(("- ", "* ")):
                    bullets.append(s[2:].strip())
                else:
                    # continuation — append to previous bullet
                    if bullets:
                        bullets[-1] = bullets[-1] + " " + s
                    else:
                        bullets.append(s)
        else:
            # Single bullet, may span multiple lines
            collapsed = " ".join(s.strip() for s in lines if s.strip())
            bullets.append(collapsed)
    return bullets


def unpack(
    bundle_path: Path,
    course_root: Path,
    date_override: str | None = None,
) -> tuple[Path, list[Path]]:
    """Unpack a bundle into markdown + image files.

    Returns (markdown_path, [image_paths...]).
    """
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    lecture_id = bundle["lecture"]
    lecture_title = bundle.get("lecture_title", "")
    exported_at_iso = bundle.get("exported_at", "")

    # Date dir: use the exported_at date if available, else today
    if date_override:
        date_str = date_override
    elif exported_at_iso:
        # ISO format like "2026-05-24T10:30:00.000Z" — take just the date portion
        date_str = exported_at_iso.split("T", 1)[0]
    else:
        date_str = _dt.date.today().isoformat()

    date_dir = course_root / "feedback" / date_str
    date_dir.mkdir(parents=True, exist_ok=True)

    rev = _next_revision_number(date_dir, lecture_id)
    md_path = date_dir / f"{lecture_id}-video-generation-feedback-{rev}.md"
    images_subdir_name = f"{lecture_id}-feedback-images-{rev}"
    images_dir = date_dir / images_subdir_name

    # Build the markdown
    lines: list[str] = []
    lines.append(f"# Lecture {lecture_id} feedback — round {rev}")
    if lecture_title:
        lines.append(f"_{lecture_title}_")
    lines.append("")
    if exported_at_iso:
        lines.append(f"Exported: {exported_at_iso}")
        lines.append("")

    written_images: list[Path] = []
    has_any_feedback = False

    for slide in bundle.get("slides", []):
        slide_n = slide.get("slide")
        title = slide.get("title", "").strip()
        text = slide.get("feedback", "").strip()
        images = slide.get("images", [])

        if not text and not images:
            continue  # skip slides with no feedback

        has_any_feedback = True
        heading = f"# Slide {slide_n}" + (f" ({title})" if title else "")
        lines.append(heading)

        bullets = _format_feedback_text_as_bullets(text)
        for b in bullets:
            lines.append(f"- {b}")

        # Write images, append references as bullets
        if images:
            images_dir.mkdir(parents=True, exist_ok=True)
            for idx, img in enumerate(images, start=1):
                name = img.get("name") or f"slide-{slide_n}-screenshot-{idx}.png"
                # Sanitize filename — strip any path components
                name = Path(name).name
                b64 = img["base64"]
                img_bytes = base64.b64decode(b64)
                img_path = images_dir / name
                img_path.write_bytes(img_bytes)
                written_images.append(img_path)
                rel = f"{images_subdir_name}/{name}"
                lines.append(f"- ![Slide {slide_n} screenshot]({rel})")

        lines.append("")

    if not has_any_feedback:
        lines.append("_No feedback recorded — all slides were left empty._")
        lines.append("")

    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return md_path, written_images


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_course_root(bundle_path: Path) -> Path:
    """Walk up from the bundle file looking for a course repo (has scripts/ + slidev/).

    Falls back to the current working directory if nothing matches.
    """
    cur = bundle_path.resolve().parent
    for _ in range(8):
        if (cur / "scripts").is_dir() and (cur / "slidev").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return Path.cwd().resolve()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="unpack_feedback.py",
        description=(
            "Unpack a feedback bundle (JSON) into markdown + image files "
            "under <course_root>/feedback/<date>/."
        ),
    )
    ap.add_argument(
        "bundle", type=Path,
        help="Path to a feedback-bundle-*.json file",
    )
    ap.add_argument(
        "--course-root", type=Path, default=None,
        help="Course repo root. Auto-detected by walking up from the bundle file.",
    )
    ap.add_argument(
        "--date", default=None,
        help="Override the date dir (YYYY-MM-DD). Defaults to the export timestamp's date.",
    )
    args = ap.parse_args(argv)

    if not args.bundle.exists():
        print(f"ERROR: bundle file not found: {args.bundle}", file=sys.stderr)
        return 1

    course_root = args.course_root.resolve() if args.course_root else _default_course_root(args.bundle)

    try:
        md_path, images = unpack(
            bundle_path=args.bundle.resolve(),
            course_root=course_root,
            date_override=args.date,
        )
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to unpack bundle: {exc}", file=sys.stderr)
        return 1

    print(f"[unpack] wrote {md_path}", file=sys.stderr)
    if images:
        print(f"[unpack] wrote {len(images)} image(s):", file=sys.stderr)
        for p in images:
            print(f"           {p}", file=sys.stderr)
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
