#!/usr/bin/env python3
"""Generate the per-lecture feedback HTML page after a render completes.

Called from render.py post-mux. Reads the script (for slide titles) + the
just-rendered assets directory (for PNG thumbnails), and writes a single
self-contained HTML file at:

    <course_root>/feedback/lecture-X.Y/index.html

The HTML embeds the logo as a base64 data URI so it works as a standalone
file (no extra path resolution needed). Thumbnail PNGs are referenced by
relative path back into the assets dir.

User opens the file in any browser, types/pastes feedback per slide, clicks
"Export bundle (JSON)" to download a feedback bundle. The companion script
unpack_feedback.py turns that JSON into the round-1-3 markdown format.

The HTML template is a string with placeholders __LIKE_THIS__ which we
substitute via str.replace. We intentionally avoid Jinja so the renderer
skill stays dep-light.
"""
from __future__ import annotations

import base64
import datetime as _dt
import re
import sys
from html import escape
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SKILL_DIR))

_TEMPLATE_PATH = _SKILL_DIR / "feedback_template.html"

# Match either `## SLIDE N: Title` (markdown form, section-02 et al.) or
# `<!-- SLIDE: N — Title -->` (HTML-comment form, sections 1/3/4/5/6/7).
# Capture (number, title) in groups (1, 2) for markdown OR (3, 4) for HTML.
# parse_slide_titles() reads the right pair depending on which matched.
_SLIDE_HEADING_WITH_TITLE_RE = re.compile(
    r"^(?:##\s+SLIDE\s+(\d+)\s*:\s*(.*?)"
    r"|<!--\s*SLIDE\s*:?\s+(\d+)\s*[-—:]?\s*(.*?)\s*-->)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Filename pattern: slide-NN-cM.png
_PNG_RE = re.compile(r"^slide-(\d+)-c(\d+)\.png$")


def find_lecture_script(lecture_id: str, course_root: Path) -> Path:
    """Locate the lecture .md file. Same logic as parse_lecture.find_lecture_file."""
    parts = lecture_id.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Lecture ID must be X.Y, got {lecture_id!r}")
    section_num = int(parts[0])
    scripts_dir = course_root / "scripts"
    candidates = list(scripts_dir.glob(f"section-{section_num:02d}-*/{lecture_id}-*.md"))
    if not candidates:
        candidates = list(scripts_dir.glob(f"section-{section_num}-*/{lecture_id}-*.md"))
    if not candidates:
        raise FileNotFoundError(
            f"No lecture file for {lecture_id!r} under {scripts_dir}"
        )
    if len(candidates) > 1:
        raise RuntimeError(f"Multiple files match lecture {lecture_id!r}")
    return candidates[0]


def parse_slide_titles(script_path: Path) -> list[tuple[int, str]]:
    """Extract (slide_n, title) tuples in document order from a script file.

    Handles both `## SLIDE N: Title` (markdown form) and
    `<!-- SLIDE: N — Title -->` (HTML-comment form). See
    _SLIDE_HEADING_WITH_TITLE_RE for the unified regex.
    """
    text = script_path.read_text(encoding="utf-8")
    out: list[tuple[int, str]] = []
    for m in _SLIDE_HEADING_WITH_TITLE_RE.finditer(text):
        # Markdown form puts captures in (1, 2); HTML-comment form in (3, 4).
        n_str = m.group(1) or m.group(3)
        title_raw = m.group(2) or m.group(4) or ""
        n = int(n_str)
        title = title_raw.strip().rstrip(":").strip()
        out.append((n, title or f"Slide {n}"))
    out.sort(key=lambda t: t[0])
    return out


def extract_lecture_title(script_path: Path, lecture_id: str) -> str:
    """Pull the H1 (# ...) from the top of the script file. Fallback to filename.

    Strips any leading 'Lecture X.Y:' / 'Lecture X.Y -' prefix so the header
    doesn't double up (the template already prepends 'Lecture X.Y ·').
    """
    text = script_path.read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    raw = m.group(1).strip() if m else script_path.stem
    # Strip a leading "Lecture X.Y: " / "Lecture X.Y - " / "Lecture X.Y — "
    prefix_re = re.compile(
        rf"^\s*Lecture\s+{re.escape(lecture_id)}\s*[:\-–—]\s*",
        re.IGNORECASE,
    )
    return prefix_re.sub("", raw).strip() or raw


def enumerate_chunks_per_slide(assets_dir: Path) -> dict[int, list[int]]:
    """Map slide_n -> sorted list of chunk indices found as slide-NN-cM.png."""
    if not assets_dir.exists():
        return {}
    by_slide: dict[int, list[int]] = {}
    for p in assets_dir.iterdir():
        m = _PNG_RE.match(p.name)
        if not m:
            continue
        slide_n = int(m.group(1))
        chunk_n = int(m.group(2))
        by_slide.setdefault(slide_n, []).append(chunk_n)
    for k in by_slide:
        by_slide[k].sort()
    return by_slide


def _logo_data_uri(course_root: Path) -> str:
    """Embed the Dyer Innovation logo-mark as a base64 data URI.

    Looked up in this order:
      1. <course_root>/slidev/public/assets/logo-mark.png
      2. <course_root>/slidev/public/logo.png
      3. <course_root>/assets/logo-mark.png

    If none exist, returns a 1x1 transparent placeholder so the <img> tag
    doesn't break.
    """
    candidates = [
        course_root / "slidev" / "public" / "assets" / "logo-mark.png",
        course_root / "slidev" / "public" / "logo.png",
        course_root / "assets" / "logo-mark.png",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            b64 = base64.b64encode(c.read_bytes()).decode("ascii")
            mime = "image/png"
            return f"data:{mime};base64,{b64}"
    # 1x1 transparent PNG fallback
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )


def _slide_card_html(
    slide_n: int,
    title: str,
    chunks: list[int],
    rel_assets_path: str,
) -> str:
    """Render one slide-card div."""
    safe_title = escape(title)
    thumbs_html_parts: list[str] = []
    if chunks:
        for c in chunks:
            png_rel = f"{rel_assets_path}/slide-{slide_n:02d}-c{c}.png"
            thumbs_html_parts.append(
                f'<div class="thumb">'
                f'<img src="{png_rel}" alt="Slide {slide_n} chunk {c}" loading="lazy" />'
                f'<span class="chunk-label">c{c}</span>'
                f'</div>'
            )
        thumbs_html = "".join(thumbs_html_parts)
        chunk_meta = f"{len(chunks)} chunk{'s' if len(chunks) != 1 else ''}"
    else:
        thumbs_html = (
            '<div style="color: var(--forest-500); font-size: 13px; font-style: italic;">'
            "No PNG thumbnails found in the assets directory. (Render the lecture first.)"
            "</div>"
        )
        chunk_meta = "no chunks"

    return f"""
<section class="slide-card" data-slide="{slide_n}" data-title="{safe_title}">
  <header>
    <span class="slide-num">Slide {slide_n}</span>
    <h3>{safe_title}</h3>
    <span class="chunk-count">{chunk_meta}</span>
  </header>
  <div class="thumbs">{thumbs_html}</div>
  <div class="editor">
    <label for="ta-{slide_n}">Feedback</label>
    <textarea id="ta-{slide_n}" placeholder="Type feedback for this slide. e.g. 'API still pronounced wrong at 0:42'."></textarea>
    <div class="dropzone" tabindex="0">
      <div class="hint">Paste a screenshot here, or drag &amp; drop image files. (Click to browse.)</div>
    </div>
    <div class="attachments"></div>
  </div>
</section>
""".strip()


def generate_feedback_html(
    lecture_id: str,
    course_root: Path,
    assets_dir: Path,
    output_dir: Path | None = None,
) -> Path:
    """Generate the per-lecture feedback HTML file.

    Returns the path to the written HTML.

    Args:
        lecture_id: e.g. "2.1"
        course_root: course repo root (resolved absolute path)
        assets_dir: directory containing slide-NN-cM.png files
                    (e.g. artifacts/lectures/.lecture-2.1-assets/)
        output_dir: optional override for output location. Defaults to
                    <course_root>/feedback/lecture-<id>/
    """
    if not _TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Feedback HTML template missing at {_TEMPLATE_PATH}. "
            "This file is part of the udemy-lecture-video-renderer skill."
        )

    script_path = find_lecture_script(lecture_id, course_root)
    slide_titles = parse_slide_titles(script_path)
    lecture_title = extract_lecture_title(script_path, lecture_id)

    if not slide_titles:
        raise ValueError(
            f"No '## SLIDE N:' headings found in {script_path}. "
            "Cannot generate feedback HTML."
        )

    chunks_by_slide = enumerate_chunks_per_slide(assets_dir)

    if output_dir is None:
        output_dir = course_root / "feedback" / f"lecture-{lecture_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_html = output_dir / "index.html"

    # Compute relative path from the HTML file's directory to the assets dir
    # so the <img src="..."> resolution works when the HTML is opened locally.
    try:
        rel_assets_path = str(
            Path(assets_dir).resolve().relative_to(out_html.parent.resolve(), walk_up=True)
        )
    except (ValueError, TypeError):
        # walk_up requires py 3.12+; fall back to os.path.relpath
        import os
        rel_assets_path = os.path.relpath(
            str(assets_dir.resolve()), str(out_html.parent.resolve())
        )

    # Build slide cards HTML
    slides_html = "\n".join(
        _slide_card_html(n, t, chunks_by_slide.get(n, []), rel_assets_path)
        for n, t in slide_titles
    )

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    out = (
        template
        .replace("__LECTURE_ID__", escape(lecture_id))
        .replace("__LECTURE_TITLE__", escape(lecture_title))
        .replace("__SLIDE_COUNT__", str(len(slide_titles)))
        .replace("__GENERATED_AT__", escape(generated_at))
        .replace("__LOGO_DATA_URI__", _logo_data_uri(course_root))
        .replace("__SLIDES_HTML__", slides_html)
    )

    out_html.write_text(out, encoding="utf-8")
    return out_html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="generate_feedback_html.py",
        description="Generate the per-lecture feedback HTML page.",
    )
    ap.add_argument("--lecture", required=True, help="Lecture ID, e.g. '2.1'")
    ap.add_argument(
        "--course-root", required=True, type=Path,
        help="Absolute path to the course repo root",
    )
    ap.add_argument(
        "--assets-dir", type=Path, default=None,
        help="Directory with slide-NN-cM.png files. "
             "Defaults to <course_root>/artifacts/lectures/.lecture-X.Y-assets/",
    )
    args = ap.parse_args(argv)

    course_root = args.course_root.resolve()
    if args.assets_dir is None:
        args.assets_dir = course_root / "artifacts" / "lectures" / f".lecture-{args.lecture}-assets"

    try:
        out = generate_feedback_html(
            lecture_id=args.lecture,
            course_root=course_root,
            assets_dir=args.assets_dir.resolve(),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"[feedback] wrote {out}", file=sys.stderr)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
