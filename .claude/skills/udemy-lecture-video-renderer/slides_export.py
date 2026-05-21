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


def _is_empty_marker_slide(slide_text: str) -> bool:
    """Check if a slide's body is only the LECTURE comment + whitespace (no rendered content)."""
    # Remove all HTML comments
    stripped = re.sub(r"<!--.*?-->", "", slide_text, flags=re.DOTALL)
    # Remove all whitespace
    stripped = re.sub(r"\s+", "", stripped)
    return stripped == ""


def _is_absorbed_part(part: str) -> bool:
    """True if slidev absorbs this part into the previous slide rather than emitting
    a new page. Empirically, slidev absorbs parts whose only content is a `<style>`
    block (deck-level CSS).
    """
    stripped = re.sub(r"<style[\s\S]*?</style>", "", part, flags=re.IGNORECASE)
    return not stripped.strip()


def _effective_slides(section_deck: Path) -> list[str]:
    """Split section into effective slidev slides (matches slidev's page count).

    Drops:
      - leading empty (before first `---`)
      - trailing empty (after last `---`)
      - style-only parts (slidev absorbs into preceding slide)
    Returns list where index 0 = slidev slide 1, index 1 = slide 2, etc.
    """
    text = section_deck.read_text(encoding="utf-8")
    parts = _SLIDE_SEP_RE.split(text)
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p for p in parts if not _is_absorbed_part(p)]


# ---------------------------------------------------------------------------
# Per-slide slidev click counting
# ---------------------------------------------------------------------------
#
# slidev's `--range` flag doesn't actually trim the exported PDF in v51.x
# (verified bug — `--range 7` still produces all 105 pages). The workaround
# is to export the WHOLE section --with-clicks once, then compute per-slide
# page offsets from the source.
#
# We count clicks per slide by recognizing the plugin's slidev component
# vocabulary:
#   - <BulletReveal :bullets="VAR" />          → clicks = len(VAR)
#   - <CodeBlockSlide :code-chunks="VAR" />    → clicks = len(VAR) - 1
#   - <CodeBlockSlide :code="VAR" />            → clicks = 1 (annotation reveal)
#   - <v-clicks>...children...</v-clicks>      → clicks = count of direct children
#   - standalone <v-click> tags                 → +1 each
# Anything else: 0 clicks.

_BULLETREVEAL_RE = re.compile(r"<BulletReveal[^>]*?:bullets\s*=\s*\"(\w+)\"", re.IGNORECASE | re.DOTALL)
_CODEBLOCK_CHUNKS_RE = re.compile(r"<CodeBlockSlide[^>]*?:code-chunks\s*=\s*\"(\w+)\"", re.IGNORECASE | re.DOTALL)
_CODEBLOCK_CODE_RE = re.compile(r"<CodeBlockSlide[^>]*?:code\s*=\s*\"(\w+)\"", re.IGNORECASE | re.DOTALL)
_VCLICK_INLINE_RE = re.compile(r"<v-click(?:\s|>|/>)", re.IGNORECASE)
_VCLICKS_BLOCK_RE = re.compile(r"<v-clicks(?:\s[^>]*)?>(.*?)</v-clicks>", re.IGNORECASE | re.DOTALL)
_VAR_ARRAY_RE_TEMPLATE = r"const\s+{var}\s*=\s*\[(.*?)\]\s*$"


def _count_array_entries(array_body: str) -> int:
    """Count top-level entries in a JS array body.

    Handles template literals (backticks) and object literals (braces).
    Falls back to a backtick-pair count if no top-level commas detected
    (covers the chunked-code pattern where each entry is one template literal).
    """
    # Strip string contents to avoid commas inside strings
    depth_paren = depth_brace = depth_bracket = 0
    in_string = False
    string_char = None
    in_template = False
    top_level_commas = 0
    i = 0
    while i < len(array_body):
        c = array_body[i]
        if in_template:
            if c == "\\":
                i += 2
                continue
            if c == "`":
                in_template = False
        elif in_string:
            if c == "\\":
                i += 2
                continue
            if c == string_char:
                in_string = False
        else:
            if c == "`":
                in_template = True
            elif c in ('"', "'"):
                in_string = True
                string_char = c
            elif c == "(":
                depth_paren += 1
            elif c == ")":
                depth_paren -= 1
            elif c == "{":
                depth_brace += 1
            elif c == "}":
                depth_brace -= 1
            elif c == "[":
                depth_bracket += 1
            elif c == "]":
                depth_bracket -= 1
            elif c == "," and depth_paren == 0 and depth_brace == 0 and depth_bracket == 0:
                top_level_commas += 1
        i += 1

    if top_level_commas > 0:
        return top_level_commas + 1  # N commas = N+1 entries (no trailing-comma adjustment)
    # No commas found at top level → assume single entry OR all-template-literal array
    # For chunked-code pattern, count backticks / 2
    bt = array_body.count("`")
    if bt >= 2:
        return bt // 2
    # Otherwise 0 (empty array) or 1 (single entry, no comma)
    return 1 if array_body.strip() else 0


def _lookup_array_in_setup(slide_text: str, var_name: str) -> int:
    """Find `const <var> = [...]` in the slide's script-setup block; return entry count."""
    pattern = re.compile(_VAR_ARRAY_RE_TEMPLATE.format(var=re.escape(var_name)), re.DOTALL | re.MULTILINE)
    m = pattern.search(slide_text)
    if not m:
        return 0
    body = m.group(1)
    # Strip trailing comma if present (e.g. `[entry1, entry2,]`)
    body = body.rstrip().rstrip(",")
    return _count_array_entries(body)


def _count_vclicks_children(block_body: str) -> int:
    """Count direct child elements inside a <v-clicks> block.

    A child is a top-level XML element. We count opening tags at the
    outermost level by tracking tag depth, ignoring nested tags.

    v-for templates count as ONE child (slidev renders all v-for instances
    as separate click reveals, but our pattern uses v-for + v-clicks parent
    only when each iteration should be its own click — for code chunks,
    this is already counted via :code-chunks length).
    """
    # Simpler heuristic: count outermost tag opens (excluding self-closing void tags)
    depth = 0
    count = 0
    i = 0
    n = len(block_body)
    while i < n:
        if block_body[i] == "<":
            # Find end of tag
            end = block_body.find(">", i)
            if end == -1:
                break
            tag = block_body[i:end + 1]
            if tag.startswith("<!--"):
                # Skip comments
                end = block_body.find("-->", i)
                if end == -1:
                    break
                i = end + 3
                continue
            if tag.startswith("</"):
                depth -= 1
            elif not tag.endswith("/>"):
                if depth == 0:
                    count += 1
                depth += 1
            else:
                # self-closing tag like <Foo />
                if depth == 0:
                    count += 1
            i = end + 1
        else:
            i += 1
    return count


def find_lecture_page_range(
    section_deck: Path,
    lecture_id: str,
) -> tuple[int, int]:
    """Return the 1-indexed (first_page, last_page) for a lecture in the PDF,
    using effective slide numbering (after dropping style-only parts that
    slidev absorbs).

    Skips the empty `<!-- LECTURE X.Y -->` marker-only slide if present —
    script SLIDE 1 plays over the lecture's Cover, not the marker.

    Returns (first_page, last_page) inclusive, 1-indexed in the effective
    slide numbering (which matches slidev's --export PDF page numbering).
    """
    slides = _effective_slides(section_deck)
    n = len(slides)

    # Locate the slides containing the target LECTURE marker and the next one
    target_slide_idx = None
    next_lecture_slide_idx = None
    for i, body in enumerate(slides):
        m = _LECTURE_MARKER_RE.search(body)
        if m and m.group(1) == lecture_id:
            target_slide_idx = i
            # search subsequent slides for next LECTURE marker
            for j in range(i + 1, n):
                nm = _LECTURE_MARKER_RE.search(slides[j])
                if nm:
                    next_lecture_slide_idx = j
                    break
            break

    if target_slide_idx is None:
        available = []
        for s in slides:
            m = _LECTURE_MARKER_RE.search(s)
            if m:
                available.append(m.group(1))
        raise ValueError(
            f"Lecture {lecture_id!r} not found in {section_deck}. "
            f"Available lectures: {available}"
        )

    end_slide_idx = next_lecture_slide_idx if next_lecture_slide_idx is not None else n
    # First content slide is target_slide_idx if its body is non-empty after
    # stripping the LECTURE comment; otherwise the marker is its own slide
    # and the cover starts at target_slide_idx + 1.
    marker_body_only = re.sub(r"<!--.*?-->", "", slides[target_slide_idx], flags=re.DOTALL).strip()
    if marker_body_only:
        # Cover is on the same slide as the marker comment
        first_slide_idx = target_slide_idx
    else:
        # Marker is its own empty slide; cover is the next slide
        first_slide_idx = target_slide_idx + 1

    last_slide_idx = end_slide_idx - 1
    # Convert to 1-indexed
    return first_slide_idx + 1, last_slide_idx + 1


def count_slidev_clicks_per_slide(section_deck: Path) -> list[int]:
    """Return list[click_count] for every EFFECTIVE slidev slide (1-indexed via list pos+1).

    Uses regex pattern-matching against the plugin's slidev component vocabulary.
    Falls back to 0 for slides whose patterns we don't recognize.
    """
    slides = _effective_slides(section_deck)
    counts: list[int] = []
    for slide_body in slides:
        clicks_from_vclicks = 0
        for m in _VCLICKS_BLOCK_RE.finditer(slide_body):
            block_body = m.group(1)
            clicks_from_vclicks += _count_vclicks_children(block_body)

        stripped = _VCLICKS_BLOCK_RE.sub("", slide_body)
        clicks_from_inline = len(_VCLICK_INLINE_RE.findall(stripped))

        clicks_from_bullets = 0
        for m in _BULLETREVEAL_RE.finditer(slide_body):
            var_name = m.group(1)
            clicks_from_bullets += _lookup_array_in_setup(slide_body, var_name)

        clicks_from_chunks = 0
        for m in _CODEBLOCK_CHUNKS_RE.finditer(slide_body):
            var_name = m.group(1)
            n = _lookup_array_in_setup(slide_body, var_name)
            if n > 0:
                clicks_from_chunks += max(0, n - 1)

        clicks_from_codeannotation = 0
        if not _CODEBLOCK_CHUNKS_RE.search(slide_body):
            for m in _CODEBLOCK_CODE_RE.finditer(slide_body):
                clicks_from_codeannotation += 1

        total = (
            clicks_from_vclicks
            + clicks_from_inline
            + clicks_from_bullets
            + clicks_from_chunks
            + clicks_from_codeannotation
        )
        counts.append(total)

    return counts


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
    """Export per-slide PNG frames for a lecture.

    **v1 LIMITATION:** This renders the FINAL state of each slide (no per-click
    visual reveals in the video). Per-click visual rendering is blocked by a
    bug in slidev v51's `--range` flag — it accepts the arg but doesn't
    actually trim the exported PDF. Until that's fixed upstream, the click
    convention plays as AUDIO-ONLY beats: narration sub-chunks separated by
    SSML breaks at [click] positions, all over the same static slide image.

    Output naming: emits ONE slide-NN-c0.png per script SLIDE (regardless of
    the script's [click] count). mux.py uses each PNG for ALL sub-chunk MP3s
    of the corresponding slide.

    If script_click_counts is None, parse_lecture is called to discover them.
    """
    section_num = int(lecture_id.split(".")[0])
    section_deck = course_root / "slidev" / f"section-{section_num}.md"
    if not section_deck.exists():
        raise FileNotFoundError(f"Slidev section deck not found: {section_deck}")

    out_dir.mkdir(parents=True, exist_ok=True)

    if script_click_counts is None:
        sys.path.insert(0, str(_SKILL_DIR))
        from parse_lecture import parse_lecture
        parsed = parse_lecture(lecture_id, course_root)
        script_click_counts = [s["click_count"] for s in parsed]

    # Step 1: full-section static PDF export (cached)
    static_pdf = Path(f"/tmp/section-{section_num}.pdf")
    export_section_pdf(section_deck, static_pdf, with_clicks=False, force=force)

    # Step 2: PNG conversion (cached on PDF mtime)
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

    # Step 3: find lecture page range using effective slide numbering
    first_page, last_page = find_lecture_page_range(section_deck, lecture_id)
    slide_count = last_page - first_page + 1
    if len(script_click_counts) != slide_count:
        raise ValueError(
            f"Slide-count mismatch for lecture {lecture_id}: "
            f"script has {len(script_click_counts)} SLIDE sections, "
            f"slidev has {slide_count} effective slides in pages {first_page}-{last_page}. "
            "Either add/remove a SLIDE in the script or a --- separator in the slidev deck."
        )
    print(
        f"[slides] lecture {lecture_id}: slidev pages {first_page}-{last_page} "
        f"({slide_count} slides). Script click counts: {script_click_counts}",
        file=sys.stderr,
    )

    # Step 4: emit one PNG per script SLIDE (final state of corresponding slidev page)
    written: list[Path] = []
    for k_zero, page_num in enumerate(range(first_page, last_page + 1)):
        k = k_zero + 1
        src = _find_page_png(section_num, page_num)
        dst = out_dir / f"slide-{k:02d}-c0.png"
        shutil.copy2(src, dst)
        written.append(dst)
        clicks = script_click_counts[k_zero]
        if clicks > 0:
            print(
                f"[slides] slide-{k:02d}-c0.png  (static page {page_num}; script declares "
                f"{clicks} [click] markers — will be rendered as audio-only sub-chunks "
                f"over this static frame; v1 limitation pending slidev --range fix)",
                file=sys.stderr,
            )
        else:
            print(
                f"[slides] slide-{k:02d}-c0.png  (static page {page_num})",
                file=sys.stderr,
            )

    print(
        f"[slides] copied {len(written)} PNG(s) to {out_dir}",
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
