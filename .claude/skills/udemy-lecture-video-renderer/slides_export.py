#!/usr/bin/env python3
"""Export Slidev slides for a lecture as PNG images.

For a given lecture ID (e.g. "2.1"), this module:
  1. Finds the Slidev section deck: <course_root>/slidev/section-N.md
  2. Exports the deck to /tmp/section-N.pdf via npx slidev export (with mtime caching)
  3. Converts the PDF to per-page PNGs via pdftoppm
  4. Determines the page range for the target lecture by parsing LECTURE markers
  5. Copies/renames the relevant PNGs to <out_dir>/slide-01.png … slide-NN.png

Usage:
    python slides_export.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets
    python slides_export.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets --force
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


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

    The Slidev PDF is 1-indexed; page 1 is the Slidev frontmatter/section-title
    slide. Each `---` separator in the deck creates a new slide/page.

    Strategy:
      1. Find the `<!-- LECTURE X.Y -->` marker line position.
      2. Find the next `<!-- LECTURE ... -->` marker or EOF.
      3. Count `---` separators between them — each one starts a new slide.
      4. The page range for the lecture = (cumulative_pages_before + 1) to
         (cumulative_pages_before + slide_count_for_lecture).

    Returns (first_page, last_page) inclusive, 1-indexed.
    """
    text = section_deck.read_text(encoding="utf-8")
    markers = list(_LECTURE_MARKER_RE.finditer(text))

    if not markers:
        raise ValueError(
            f"No LECTURE markers found in {section_deck}. "
            "Check that the deck has <!-- LECTURE X.Y — Title --> comments."
        )

    # Find the target lecture marker
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
    # Content for this lecture ends at next LECTURE marker or EOF
    next_start = (
        markers[target_idx + 1].start()
        if target_idx + 1 < len(markers)
        else len(text)
    )
    lecture_text = text[target_marker.start():next_start]

    # Count slides in this lecture (each --- separator = one slide boundary)
    # The first --- after the LECTURE marker opens slide 1 of the lecture;
    # the content between separators is the slide body.
    # Number of slides = number of --- separators in this lecture's chunk.
    slide_count = _count_slides_between(text, target_marker.start(), next_start)

    if slide_count == 0:
        raise ValueError(
            f"No slide separators (---) found for lecture {lecture_id} in {section_deck}."
        )

    # Calculate cumulative page offset before this lecture
    # Count all --- separators from text start up to this lecture's marker.
    # Page 1 = the Slidev frontmatter block (before any ---).
    # Each --- separator adds one page.
    pages_before = _count_slides_between(text, 0, target_marker.start())
    # +1 because the PDF is 1-indexed and page 1 is before the first ---
    first_page = pages_before + 1
    last_page = first_page + slide_count - 1

    return first_page, last_page


# ---------------------------------------------------------------------------
# Export and slice
# ---------------------------------------------------------------------------

def export_section_pdf(
    section_deck: Path,
    pdf_path: Path,
    force: bool = False,
    timeout: int = 300,
) -> None:
    """Export the Slidev section deck to PDF if not cached."""
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

    print(
        f"[slides] exporting {section_deck.name} → {pdf_path} ...",
        file=sys.stderr,
        flush=True,
    )

    result = subprocess.run(
        [
            "npx", "slidev", "export",
            section_deck.name,
            "--output", str(pdf_path),
        ],
        cwd=section_deck.parent,
        capture_output=False,  # Let slidev output stream to terminal
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

    prefix is used as the output file prefix; pdftoppm appends -NNN.png.
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
        raise RuntimeError(
            f"pdftoppm failed: {result.stderr.strip()}"
        )

    parent = prefix.parent
    stem = prefix.name
    pngs = sorted(parent.glob(f"{stem}-*.png"))
    if not pngs:
        raise RuntimeError(
            f"pdftoppm produced no PNG files with prefix {prefix}"
        )
    return pngs


def export_slides(
    lecture_id: str,
    course_root: Path,
    out_dir: Path,
    force: bool = False,
) -> list[Path]:
    """Export and slice slides for a lecture. Returns list of slide PNG paths."""
    section_num = int(lecture_id.split(".")[0])
    section_deck = course_root / "slidev" / f"section-{section_num}.md"

    if not section_deck.exists():
        raise FileNotFoundError(
            f"Slidev section deck not found: {section_deck}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: export section PDF
    pdf_path = Path(f"/tmp/section-{section_num}.pdf")
    export_section_pdf(section_deck, pdf_path, force=force)

    # Step 2: convert to PNGs (only if PDF is newer than existing PNGs or force)
    png_prefix = Path(f"/tmp/section-{section_num}-page")
    # Determine if we need to re-run pdftoppm
    existing_pngs = sorted(Path("/tmp").glob(f"section-{section_num}-page-*.png"))
    needs_pdftoppm = (
        force
        or not existing_pngs
        or any(
            p.stat().st_mtime < pdf_path.stat().st_mtime
            for p in existing_pngs
        )
    )

    if needs_pdftoppm:
        print(
            f"[slides] running pdftoppm on {pdf_path.name} ...",
            file=sys.stderr,
            flush=True,
        )
        existing_pngs = pdf_to_pngs(pdf_path, png_prefix)
        print(
            f"[slides] produced {len(existing_pngs)} page PNGs",
            file=sys.stderr,
        )
    else:
        print(
            f"[slides] {len(existing_pngs)} page PNGs cached, skipping pdftoppm",
            file=sys.stderr,
        )

    # Step 3: determine page range for the target lecture
    first_page, last_page = find_lecture_page_range(section_deck, lecture_id)
    slide_count = last_page - first_page + 1

    print(
        f"[slides] lecture {lecture_id}: slidev pages {first_page}-{last_page} "
        f"→ slide-01.png to slide-{slide_count:02d}.png",
        file=sys.stderr,
    )

    # Step 4: copy/rename relevant PNGs to out_dir
    # pdftoppm names pages as -001, -002, etc. (3-digit zero-padded)
    written: list[Path] = []
    for i, page_num in enumerate(range(first_page, last_page + 1), start=1):
        # Find the source PNG — pdftoppm may use -1, -01, -001 depending on total pages
        src = None
        for candidate in [
            Path(f"/tmp/section-{section_num}-page-{page_num:03d}.png"),
            Path(f"/tmp/section-{section_num}-page-{page_num:02d}.png"),
            Path(f"/tmp/section-{section_num}-page-{page_num}.png"),
        ]:
            if candidate.exists():
                src = candidate
                break

        if src is None:
            raise FileNotFoundError(
                f"Expected page {page_num} PNG not found at /tmp/section-{section_num}-page-*.png. "
                f"Total pages available: {len(existing_pngs)}"
            )

        dst = out_dir / f"slide-{i:02d}.png"
        shutil.copy2(src, dst)
        written.append(dst)

    print(
        f"[slides] copied {len(written)} slide PNGs to {out_dir}",
        file=sys.stderr,
    )
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="slides_export.py",
        description="Export Slidev slides for a lecture as PNG images.",
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
        help="Directory to write slide-NN.png files",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-export and re-slice, ignoring all caches",
    )
    args = ap.parse_args(argv)

    try:
        written = export_slides(
            lecture_id=args.lecture,
            course_root=args.course_root,
            out_dir=args.out_dir,
            force=args.force,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"[slides] {len(written)} slide PNG(s) ready in {args.out_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
