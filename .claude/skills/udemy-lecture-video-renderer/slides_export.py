#!/usr/bin/env python3
"""Export Slidev slides for a lecture as per-click PNG frames.

For a given lecture ID (e.g. "2.1") and a list of per-slide script-declared
click counts, this module:

  1. Finds the Slidev section deck: <course_root>/slidev/section-N.md
  2. Exports the deck to /tmp/section-N.pdf (static, one page per slide)
  3. Converts the PDF to per-page PNGs via pdftoppm
  4. Determines the page range for the target lecture by parsing LECTURE markers
  5. For each lecture slide K (1-indexed within the lecture):
     - If script_click_counts[K-1] == 0: copies the static PNG → slide-KK-c0.png
     - If script_click_counts[K-1] > 0: runs a per-slide
       `slidev export --range P --with-clicks` export for that slide, slices
       into per-click frames → slide-KK-c0.png, slide-KK-c1.png, ...
  6. Hard-validates that slidev's per-click frame count matches the script's
     declared click count for each click-aware slide. Mismatch → abort.

Output naming convention (consumed by mux.py):
    slide-NN-cM.png   where NN = slide index (1-padded), M = click state (0..N_clicks)
                      Click state 0 is the initial state, N_clicks is final.

For slides with script_click_count == 0, exactly one file is emitted:
slide-NN-c0.png (the final-revealed slidev state).

Usage:
    python slides_export.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets
    # Optional: pass click counts as a comma-separated string aligned to slides
    python slides_export.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets --click-counts 0,0,2,1,0,2,0,0

When --click-counts is omitted, the script is parsed via parse_lecture.py
to discover the counts automatically.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Lecture boundary parsing
# ---------------------------------------------------------------------------

# Matches <!-- LECTURE X.Y — Title --> (any dash variant, optional whitespace)
_LECTURE_MARKER_RE = re.compile(
    r"<!--\s+LECTURE\s+([\d]+\.[\d]+)\s*[—\-–].*?-->",
    re.IGNORECASE,
)

# A Slidev slide separator (--- on its own line)
_SLIDE_SEP_RE = re.compile(r"^---\s*$", re.MULTILINE)


def _count_slides_between(text: str, start: int, end: int) -> int:
    """Count the number of --- slide separators between two character positions."""
    return len(_SLIDE_SEP_RE.findall(text[start:end]))


def find_lecture_page_range(
    section_deck: Path,
    lecture_id: str,
) -> tuple[int, int]:
    """Return the 1-indexed (first_page, last_page) for a lecture in the PDF.

    The static (no --with-clicks) Slidev PDF is 1-indexed; page 1 is the
    Slidev frontmatter/section-title slide. Each `---` separator creates a
    new slide/page.

    Returns (first_page, last_page) inclusive, 1-indexed.
    """
    text = section_deck.read_text(encoding="utf-8")
    markers = list(_LECTURE_MARKER_RE.finditer(text))

    if not markers:
        raise ValueError(
            f"No LECTURE markers found in {section_deck}. "
            "Check that the deck has <!-- LECTURE X.Y — Title --> comments."
        )

    target_idx = None
    for i, m in enumerate(markers):
        if m.group(1) == lecture_id:
            target_idx = i
            break

    if target_idx is None:
        available = [m.group(1) for m in markers]
        raise ValueError(
            f"Lecture {lecture_id!r} not found in {section_deck}. "
            f"Available lectures: {available}"
        )

    target_marker = markers[target_idx]
    next_start = (
        markers[target_idx + 1].start()
        if target_idx + 1 < len(markers)
        else len(text)
    )
    slide_count = _count_slides_between(text, target_marker.start(), next_start)
    if slide_count == 0:
        raise ValueError(
            f"No slide separators (---) found for lecture {lecture_id} in {section_deck}."
        )

    pages_before = _count_slides_between(text, 0, target_marker.start())
    first_page = pages_before + 1
    last_page = first_page + slide_count - 1
    return first_page, last_page


# ---------------------------------------------------------------------------
# Slidev export
# ---------------------------------------------------------------------------

def export_section_pdf(
    section_deck: Path,
    pdf_path: Path,
    with_clicks: bool = False,
    page_range: str | None = None,
    force: bool = False,
    timeout: int = 300,
) -> None:
    """Export a Slidev deck to PDF.

    - with_clicks: pass --with-clicks (one PDF page per click state)
    - page_range: pass --range, e.g. "5" or "3-10". None = full deck.
    """
    if (
        not force
        and pdf_path.exists()
        and pdf_path.stat().st_size > 0
        and pdf_path.stat().st_mtime > section_deck.stat().st_mtime
    ):
        print(
            f"[slides] {pdf_path.name} cached (mtime ok), skipping export",
            file=sys.stderr,
        )
        return

    args = ["npx", "slidev", "export", section_deck.name, "--output", str(pdf_path)]
    if with_clicks:
        args.append("--with-clicks")
    if page_range:
        args.extend(["--range", page_range])

    label = f"{section_deck.name}"
    if page_range:
        label += f" --range {page_range}"
    if with_clicks:
        label += " --with-clicks"
    print(
        f"[slides] exporting {label} → {pdf_path} ...",
        file=sys.stderr,
        flush=True,
    )

    result = subprocess.run(
        args,
        cwd=section_deck.parent,
        capture_output=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Slidev export failed with exit code {result.returncode}. "
            "Check that Playwright is installed: npx playwright install chromium"
        )
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(
            f"Slidev export reported success but {pdf_path} was not written."
        )
    print(
        f"[slides] exported {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)",
        file=sys.stderr,
    )


def pdf_to_pngs(pdf_path: Path, prefix: Path, resolution: int = 150) -> list[Path]:
    """Convert a PDF to per-page PNGs via pdftoppm.

    Returns sorted list of produced PNG paths.
    """
    result = subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r", str(resolution),
            str(pdf_path),
            str(prefix),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr.strip()}")
    parent = prefix.parent
    stem = prefix.name
    pngs = sorted(parent.glob(f"{stem}-*.png"))
    if not pngs:
        raise RuntimeError(f"pdftoppm produced no PNG files with prefix {prefix}")
    return pngs


def _find_page_png(section_num: int, page_num: int) -> Path:
    """Find a pdftoppm-produced page PNG, accounting for variable padding."""
    for candidate in [
        Path(f"/tmp/section-{section_num}-page-{page_num:03d}.png"),
        Path(f"/tmp/section-{section_num}-page-{page_num:02d}.png"),
        Path(f"/tmp/section-{section_num}-page-{page_num}.png"),
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Expected static PNG for section {section_num} page {page_num} not found "
        f"at /tmp/section-{section_num}-page-*.png"
    )


# ---------------------------------------------------------------------------
# Main: per-click-aware export
# ---------------------------------------------------------------------------

def export_slides(
    lecture_id: str,
    course_root: Path,
    out_dir: Path,
    force: bool = False,
    script_click_counts: list[int] | None = None,
) -> list[Path]:
    """Export per-click slide frames for a lecture. Returns list of written PNGs.

    If script_click_counts is None, parse_lecture is called to discover them.
    """
    section_num = int(lecture_id.split(".")[0])
    section_deck = course_root / "slidev" / f"section-{section_num}.md"
    if not section_deck.exists():
        raise FileNotFoundError(f"Slidev section deck not found: {section_deck}")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Auto-discover click counts from script if not provided
    if script_click_counts is None:
        sys.path.insert(0, str(_SKILL_DIR))
        from parse_lecture import parse_lecture
        parsed = parse_lecture(lecture_id, course_root)
        script_click_counts = [s["click_count"] for s in parsed]

    # Step 1: export the section PDF (static, no --with-clicks) — cached
    static_pdf = Path(f"/tmp/section-{section_num}.pdf")
    export_section_pdf(section_deck, static_pdf, with_clicks=False, force=force)

    # Step 2: convert to PNGs (cached on PDF mtime)
    png_prefix = Path(f"/tmp/section-{section_num}-page")
    existing_pngs = sorted(Path("/tmp").glob(f"section-{section_num}-page-*.png"))
    needs_pdftoppm = (
        force
        or not existing_pngs
        or any(p.stat().st_mtime < static_pdf.stat().st_mtime for p in existing_pngs)
    )
    if needs_pdftoppm:
        print(
            f"[slides] running pdftoppm on {static_pdf.name} ...",
            file=sys.stderr,
            flush=True,
        )
        existing_pngs = pdf_to_pngs(static_pdf, png_prefix)
        print(f"[slides] produced {len(existing_pngs)} static PNGs", file=sys.stderr)
    else:
        print(
            f"[slides] {len(existing_pngs)} static PNGs cached, skipping pdftoppm",
            file=sys.stderr,
        )

    # Step 3: find lecture page range
    first_page, last_page = find_lecture_page_range(section_deck, lecture_id)
    slide_count = last_page - first_page + 1
    if len(script_click_counts) != slide_count:
        raise ValueError(
            f"Slide-count mismatch for lecture {lecture_id}: "
            f"script has {len(script_click_counts)} SLIDE sections, "
            f"slidev has {slide_count} slides in pages {first_page}-{last_page}. "
            "Either add/remove a SLIDE in the script or a --- separator in the slidev deck."
        )
    print(
        f"[slides] lecture {lecture_id}: slidev pages {first_page}-{last_page} "
        f"({slide_count} slides). Script click counts: {script_click_counts}",
        file=sys.stderr,
    )

    # Step 4: per-slide emit
    written: list[Path] = []
    for k_zero, page_num in enumerate(range(first_page, last_page + 1)):
        k = k_zero + 1  # 1-indexed for output naming
        clicks = script_click_counts[k_zero]

        if clicks == 0:
            # Copy static page → slide-KK-c0.png
            src = _find_page_png(section_num, page_num)
            dst = out_dir / f"slide-{k:02d}-c0.png"
            shutil.copy2(src, dst)
            written.append(dst)
            print(
                f"[slides] slide-{k:02d}-c0.png  (static page {page_num})",
                file=sys.stderr,
            )
            continue

        # script_clicks > 0 → per-slide export with --with-clicks
        slide_pdf = Path(
            f"/tmp/section-{section_num}-slide-{page_num}-clicks.pdf"
        )
        slide_prefix = Path(
            f"/tmp/section-{section_num}-slide-{page_num}-clicks-page"
        )

        # Cache check
        slide_pdf_stale = (
            force
            or not slide_pdf.exists()
            or slide_pdf.stat().st_mtime < section_deck.stat().st_mtime
        )
        if slide_pdf_stale:
            # Remove any stale per-click PNGs for this slide before re-export
            for stale in Path("/tmp").glob(slide_prefix.name + "-*.png"):
                stale.unlink()
            export_section_pdf(
                section_deck,
                slide_pdf,
                with_clicks=True,
                page_range=str(page_num),
                force=True,  # we already decided to re-export
            )

        # Convert (or reuse) per-click PNGs
        click_pngs = sorted(Path("/tmp").glob(slide_prefix.name + "-*.png"))
        if not click_pngs or slide_pdf_stale:
            click_pngs = pdf_to_pngs(slide_pdf, slide_prefix)

        # Validate slidev clicks match script clicks
        expected = clicks + 1
        if len(click_pngs) != expected:
            raise ValueError(
                f"Click-count mismatch on slide {k} (slidev page {page_num}) of lecture "
                f"{lecture_id}: script declares {clicks} [click] markers "
                f"(expecting {expected} frames), but slidev produced {len(click_pngs)} "
                f"frames for that slide. Update either the script's [click] count or the "
                f"slidev component to match (typically a :code-chunks array size, a "
                f"<v-clicks> child count, or a BulletReveal :bullets array size)."
            )

        # Copy each click state → slide-KK-cM.png
        for m, src in enumerate(click_pngs):
            dst = out_dir / f"slide-{k:02d}-c{m}.png"
            shutil.copy2(src, dst)
            written.append(dst)
        print(
            f"[slides] slide-{k:02d}-c0..c{clicks}.png  ({expected} per-click frames "
            f"from page {page_num} --with-clicks)",
            file=sys.stderr,
        )

    print(
        f"[slides] copied {len(written)} per-click PNG(s) to {out_dir}",
        file=sys.stderr,
    )
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="slides_export.py",
        description="Export per-click Slidev slide frames for a lecture.",
    )
    ap.add_argument("--lecture", required=True, help="Lecture ID, e.g. '2.1'")
    ap.add_argument(
        "--course-root",
        required=True,
        type=Path,
        help="Absolute path to the course repo root",
    )
    ap.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Directory to write slide-NN-cM.png files",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-export and re-slice, ignoring all caches",
    )
    ap.add_argument(
        "--click-counts",
        default=None,
        help=(
            "Comma-separated per-slide [click] counts (e.g. '0,0,2,1,0,2,0,0'). "
            "If omitted, the lecture script is parsed to discover counts."
        ),
    )
    args = ap.parse_args(argv)

    script_click_counts = None
    if args.click_counts:
        try:
            script_click_counts = [int(x.strip()) for x in args.click_counts.split(",")]
        except ValueError as exc:
            print(
                f"ERROR: --click-counts must be comma-separated ints, got {args.click_counts!r}",
                file=sys.stderr,
            )
            return 1

    try:
        written = export_slides(
            lecture_id=args.lecture,
            course_root=args.course_root,
            out_dir=args.out_dir,
            force=args.force,
            script_click_counts=script_click_counts,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"[slides] {len(written)} PNG(s) ready in {args.out_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
