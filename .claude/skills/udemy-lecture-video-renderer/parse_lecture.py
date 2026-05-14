#!/usr/bin/env python3
"""Parse a lecture .md script into per-slide narration chunks.

Output: JSON array of {slide_n: int, narration_text: str, click_count: int}

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

# [click] markers → SSML break
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


def convert_click_markers(text: str) -> tuple[str, int]:
    """Replace [click] with SSML <break time="0.8s" />. Return (text, count)."""
    count = len(_CLICK_RE.findall(text))
    text = _CLICK_RE.sub('<break time="0.8s" />', text)
    return text, count


def clean_whitespace(text: str) -> str:
    """Collapse multiple blank lines and strip leading/trailing whitespace."""
    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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

        # Apply click conversion
        narration_with_breaks, click_count = convert_click_markers(narration_raw)

        # Clean up whitespace
        narration_clean = clean_whitespace(narration_with_breaks)

        slides.append({
            "slide_n": slide_n,
            "narration_text": narration_clean,
            "click_count": click_count,
        })

    # Sort by slide number (should already be ordered, but be safe)
    slides.sort(key=lambda s: s["slide_n"])

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
