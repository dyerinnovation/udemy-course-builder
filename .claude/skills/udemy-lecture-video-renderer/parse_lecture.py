#!/usr/bin/env python3
"""Parse a lecture .md script into per-slide narration sub-chunks.

Output: JSON array of:
    {
      "slide_n": int,
      "narrations": [str, str, ...],   # one sub-chunk per click state
      "click_count": int                # len(narrations) - 1
    }

Each [click] marker in the script splits the slide's narration into the
next sub-chunk. N [click] markers in a slide's body produce N+1 narrations:
sub-chunk 0 plays while the slide is in initial state, sub-chunk K plays
after click K reveals chunk K. This drives the click-aware renderer in
slides_export.py / tts_render.py / mux.py.

For slides with zero [click] markers, narrations has length 1 (full text)
and click_count is 0 — those slides render as a single frame regardless of
slidev clicks. This means BulletReveal-style slides where author hasn't
opted into per-click narration alignment still "just work".

Usage:
    python parse_lecture.py --lecture 2.1 --course-root /path/to/course
    python parse_lecture.py --lecture 2.1 --course-root /path/to/course | python -m json.tool

The script discovers the lecture file by glob-matching:
    <course_root>/scripts/section-NN-*/X.Y-*.md
where N is the section number parsed from the lecture ID (e.g. "2" from "2.1").
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Matches ## SLIDE N: Title  (entire heading line, any amount of whitespace, case-insensitive N)
_SLIDE_HEADING_RE = re.compile(r"^##\s+SLIDE\s+(\d+)\s*:.*$", re.IGNORECASE | re.MULTILINE)

# Strip YAML frontmatter block (--- ... ---)
_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n.*?\n---\s*\n", re.DOTALL)

# Lines to strip entirely (not narrated)
_VISUAL_RE = re.compile(r"^\s*\*\*Visual\*\*\s*:.*$", re.MULTILINE | re.IGNORECASE)
_CAMERA_RE = re.compile(r"^\s*\*\*Camera\s+direction\*\*\s*:.*$", re.MULTILINE | re.IGNORECASE)

# Fenced code blocks (``` ... ```)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

# [click] markers — sub-chunk boundaries within a slide's narration
_CLICK_RE = re.compile(r"\[click\]", re.IGNORECASE)

# Horizontal rules used as section dividers in scripts (--- on its own line)
_HR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)

# Top-of-file metadata lines ONLY (e.g. **Section**: ..., **Duration**: ..., **Status**: ...)
# These appear before the first ## SLIDE heading. We strip the pre-slide preamble
# by slicing the text at the first ## SLIDE heading rather than applying this globally.
_META_LINE_RE = re.compile(r"^\s*\*\*\w[^*]*\*\*\s*:.*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------

def find_lecture_file(lecture_id: str, course_root: Path) -> Path:
    """Locate the lecture .md file for a given lecture ID like '2.1'."""
    parts = lecture_id.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Lecture ID must be in X.Y format, got: {lecture_id!r}")
    section_num = int(parts[0])
    section_glob = f"section-{section_num:02d}-*"
    scripts_dir = course_root / "scripts"
    candidates = list(scripts_dir.glob(f"{section_glob}/{lecture_id}-*.md"))
    if not candidates:
        # Also try without zero-padding on the section number
        candidates = list(scripts_dir.glob(f"section-{section_num}-*/{lecture_id}-*.md"))
    if not candidates:
        raise FileNotFoundError(
            f"No lecture file found for {lecture_id!r} under {scripts_dir}. "
            f"Expected: {scripts_dir}/{section_glob}/{lecture_id}-*.md"
        )
    if len(candidates) > 1:
        raise RuntimeError(
            f"Multiple files match lecture {lecture_id!r}: "
            + ", ".join(str(p) for p in candidates)
        )
    return candidates[0]


def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter if present."""
    return _FRONTMATTER_RE.sub("", text, count=1)


def strip_non_narrated_lines(text: str) -> str:
    """Remove **Visual**: and **Camera direction**: lines."""
    text = _VISUAL_RE.sub("", text)
    text = _CAMERA_RE.sub("", text)
    return text


def strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks (code is on screen, not narrated)."""
    return _CODE_FENCE_RE.sub("", text)


def strip_metadata_lines(text: str) -> str:
    """Remove top-of-file metadata lines like **Section**: ... **Duration**: ...

    Only strips lines in the preamble before the first ## SLIDE heading.
    Lines WITHIN slide content (e.g. **Exam Trap**: ...) are intentional narration
    and must be preserved.
    """
    first_slide = _SLIDE_HEADING_RE.search(text)
    if not first_slide:
        # No slides found — strip globally (will fail later with a clear error)
        return _META_LINE_RE.sub("", text)
    preamble = text[: first_slide.start()]
    rest = text[first_slide.start():]
    return _META_LINE_RE.sub("", preamble) + rest


def split_at_clicks(text: str) -> list[str]:
    """Split narration text at [click] markers into sub-chunks.

    Returns a list of clean text fragments. N [click] markers produce N+1
    sub-chunks. Each sub-chunk has surrounding whitespace stripped.
    Empty fragments are collapsed to a single space so downstream TTS doesn't
    fail on zero-length text (e.g. consecutive [click] markers).
    """
    parts = _CLICK_RE.split(text)
    cleaned = []
    for p in parts:
        s = p.strip()
        cleaned.append(s if s else " ")
    return cleaned


# Ellipses (ASCII ... or Unicode …) get vocalized as long pauses by
# ElevenLabs — almost always not what the author wants. Strip globally in
# narration cleanup. If a deliberate pause is needed, the author should
# use SSML <break time="0.8s"/> or write "pause" as a stage direction.
# (Round-4 add: caught on lecture 2.1 SLIDE 9 where {"content": "..."}
# in a JSON example was producing 1-2s of dead air.)
_ELLIPSIS_RE = re.compile(r"\.{3,}|…")


def clean_whitespace(text: str) -> str:
    """Collapse multiple blank lines, strip ellipses, trim outer whitespace."""
    # Round-4: strip ellipses BEFORE blank-line collapse so any whitespace
    # exposed by stripping `"..."` (e.g. `"content": "..."` -> `"content": ""`)
    # still collapses naturally.
    text = _ELLIPSIS_RE.sub("", text)
    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Strip inline markdown decoration so it doesn't bleed into TTS narration.
# ElevenLabs multilingual_v2 may vocalize literal asterisks as "asterisk
# asterisk", so we strip emphasis markers while preserving the text content.
_BOLD_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_LIST_BULLET_RE = re.compile(r"^[ \t]*[-*][ \t]+", re.MULTILINE)


def strip_markdown_decoration(text: str) -> str:
    """Remove inline markdown emphasis + list bullets from narration text.

    Drops the syntactic markers but preserves the textual content:
      - **bold**    → bold
      - *italic*    → italic
      - "- item"    → "item"
    Backticks around code spans are intentionally LEFT IN PLACE — most TTS
    engines silently skip backticks, so they act as a soft separator without
    altering prosody. If a smoke test shows otherwise, expand this function.
    """
    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    text = _LIST_BULLET_RE.sub("", text)
    return text


# ---------------------------------------------------------------------------
# Pronunciation pre-flight check (round-3 add)
# ---------------------------------------------------------------------------

# Match snake_case identifiers in narration text. Lowercase only — uppercase
# variants are rare in narration and skipping them avoids false matches on
# things like "XML_data" or environment variables (which usually live in code
# blocks, not narration anyway).
_SNAKE_ID_RE = re.compile(r"\b[a-z][a-z]+_[a-z][a-z_]*\b")

# Match grapheme lines in a PLS file. Cheap regex extraction — the PLS files
# are simple enough we don't need full XML parsing here, and avoiding the
# stdlib xml.etree dep keeps this module dep-light.
_GRAPHEME_RE = re.compile(r"<grapheme>([^<]+)</grapheme>")


def _scan_pls_graphemes(course_root: Path) -> set[str]:
    """Read both PLS files (course + plugin template) and return the union of
    all <grapheme> values. Used by _audit_pronunciation to confirm narration
    identifiers have pronunciation overrides.
    """
    graphemes: set[str] = set()

    # Course override PLS (may not exist)
    course_pls = course_root / "course-metadata" / "pronunciation.pls"
    if course_pls.exists():
        graphemes.update(_GRAPHEME_RE.findall(course_pls.read_text(encoding="utf-8")))

    # Plugin template PLS (lives next to this script)
    template_pls = Path(__file__).parent / "pronunciation.template.pls"
    if template_pls.exists():
        graphemes.update(_GRAPHEME_RE.findall(template_pls.read_text(encoding="utf-8")))

    return graphemes


def _audit_pronunciation(slides: list[dict], course_root: Path) -> None:
    """Scan narration text for underscored identifiers not in the merged PLS.

    Prints a [parse] WARNING per missing identifier to stderr. Doesn't fail —
    the author may have a reason to skip (one-off use where TTS handles it OK,
    or the term is in a code block that gets stripped). The warning just makes
    the trap visible BEFORE TTS spend.

    This catches the same class of bug seen in round-1 (stop_reason) and
    round-3 (stop_sequence) — identifiers like `tool_use` and `max_tokens`
    that get mangled by ElevenLabs unless given an explicit alias. See
    playbook.md "Pronunciation gotchas" for the fix pattern.
    """
    graphemes = _scan_pls_graphemes(course_root)
    if not graphemes:
        # No PLS files at all — author hasn't set up pronunciation overrides
        # for this course. Don't spam warnings; tts_render will fail more
        # informatively if needed.
        return

    # Walk every narration sub-chunk in every slide
    found: dict[str, list[int]] = {}  # identifier -> [slide_n, ...]
    for slide in slides:
        slide_n = slide["slide_n"]
        for sub_chunk in slide["narrations"]:
            for match in _SNAKE_ID_RE.finditer(sub_chunk):
                ident = match.group(0)
                if ident in graphemes:
                    continue
                found.setdefault(ident, []).append(slide_n)

    if not found:
        return

    print(
        f"[parse] PRONUNCIATION AUDIT: {len(found)} underscored identifier(s) in "
        "narration are missing from the merged PLS dict.",
        file=sys.stderr,
    )
    print(
        "         ElevenLabs will likely mangle the underscore (e.g. "
        "'stop_sequence' -> 'stop harsh sequence').",
        file=sys.stderr,
    )
    print(
        "         Add a <lexeme> entry to course-metadata/pronunciation.pls "
        "for each. Example pattern:",
        file=sys.stderr,
    )
    for ident in sorted(found):
        # Suggest the natural-reading alias by replacing _ with space
        suggested_alias = ident.replace("_", " ")
        slide_list = sorted(set(found[ident]))
        slide_str = ", ".join(f"SLIDE {n}" for n in slide_list)
        print(
            f"           <lexeme><grapheme>{ident}</grapheme>"
            f"<alias>{suggested_alias}</alias></lexeme>  "
            f"# {slide_str}",
            file=sys.stderr,
        )


def parse_lecture(lecture_id: str, course_root: Path) -> list[dict]:
    """Parse a lecture .md file into per-slide narration data.

    Returns a list of dicts:
      [{slide_n: int, narration_text: str, click_count: int}, ...]

    Slides are ordered by slide number. The ## SLIDE N: heading line is
    NOT included in narration_text.
    """
    lecture_path = find_lecture_file(lecture_id, course_root)
    raw = lecture_path.read_text(encoding="utf-8")

    # Stage 1: strip structural noise
    text = strip_frontmatter(raw)
    text = strip_metadata_lines(text)
    text = strip_code_blocks(text)
    text = strip_non_narrated_lines(text)
    # Remove horizontal rules (--- dividers between slides in the script)
    text = _HR_RE.sub("", text)

    # Stage 2: split on ## SLIDE N: headings
    # Find all heading positions
    headings = list(_SLIDE_HEADING_RE.finditer(text))
    if not headings:
        raise ValueError(
            f"No '## SLIDE N:' headings found in {lecture_path}. "
            "Check that the lecture script uses the correct heading format."
        )

    slides: list[dict] = []
    for i, match in enumerate(headings):
        slide_n = int(match.group(1))
        # Content starts after the heading line
        start = match.end()
        # Content ends at the next heading or end of text
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        narration_raw = text[start:end]

        # Strip markdown decoration that would otherwise leak into TTS
        narration_stripped = strip_markdown_decoration(narration_raw)
        # Final whitespace cleanup happens per-subchunk after splitting.

        # Split at [click] markers into N+1 sub-chunks
        sub_chunks_raw = split_at_clicks(narration_stripped)
        narrations = [clean_whitespace(c) for c in sub_chunks_raw]
        click_count = len(narrations) - 1

        slides.append({
            "slide_n": slide_n,
            "narrations": narrations,
            "click_count": click_count,
        })

    # Sort by slide number (should already be ordered, but be safe)
    slides.sort(key=lambda s: s["slide_n"])

    # Pre-flight: audit narration for underscored identifiers missing from the
    # merged PLS dict. Warns to stderr; never fails. See _audit_pronunciation.
    _audit_pronunciation(slides, course_root)

    return slides


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="parse_lecture.py",
        description="Extract per-slide narration from a lecture .md script (JSON output).",
    )
    ap.add_argument("--lecture", required=True, help="Lecture ID, e.g. '2.1'")
    ap.add_argument(
        "--course-root",
        required=True,
        type=Path,
        help="Absolute path to the course repo root",
    )
    args = ap.parse_args(argv)

    try:
        slides = parse_lecture(args.lecture, args.course_root)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(slides, indent=2, ensure_ascii=False))
    print(
        f"[parse] lecture {args.lecture}: {len(slides)} slide(s) parsed",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
