#!/usr/bin/env python3
"""
Parse Udemy lecture markdown files into structured slide data.

Extracts slide content, visual descriptions, [click] markers, speaker notes,
and slide type hints from the udemy-lecture-writer output format.

Usage:
    python parse_lecture.py <markdown_path> [--output <json_path>]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class SlideSegment:
    """A segment of content within a slide (separated by [click] markers)."""
    narration: str
    is_reveal: bool  # True if this segment appears after a [click]


@dataclass
class SlideContent:
    """Represents a single slide's content."""
    slide_number: int
    title: str
    slide_type: str           # TITLE, CONTENT, CODE, COMPARISON, EXAM_TIP, TAKEAWAY, SECTION, QUIZ
    visual_description: str
    segments: list            # list of SlideSegment dicts
    speaker_notes: str        # full narration joined
    has_clicks: bool          # whether slide has [click] progressive reveals
    code_block: Optional[str] = None  # extracted code if present


@dataclass
class LectureMetadata:
    """Lecture header information."""
    lecture_number: str       # e.g. "2.3"
    title: str
    section: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None


@dataclass
class ParsedLecture:
    """Complete parsed lecture structure."""
    metadata: LectureMetadata
    slides: list              # list of SlideContent dicts


def determine_slide_type(title: str, visual: str, narration: str) -> str:
    """Determine slide type from title and visual description."""
    title_lower = title.lower()
    visual_lower = visual.lower()

    # Exam tip
    if any(x in title_lower for x in ['exam tip', 'exam trap']):
        return 'EXAM_TIP'

    # Key takeaways / summary
    if any(x in title_lower for x in ['key takeaway', 'takeaway', 'what to remember', 'summary']):
        return 'TAKEAWAY'

    # Title / opener slides
    if any(x in visual_lower for x in ['title slide', 'course opener', 'centered title', 'full dark']):
        return 'TITLE'

    # Section divider
    if any(x in visual_lower for x in ['section divider', 'section header', 'chapter']):
        return 'SECTION'

    # Code slides
    if any(x in visual_lower for x in ['code block', 'code example', 'code snippet', 'syntax', 'monospace']):
        return 'CODE'

    # Comparison / two-column
    if any(x in visual_lower for x in ['split', 'comparison', 'vs', 'left side', 'right side', 'two column', 'contrast']):
        return 'COMPARISON'

    # Quiz slide
    if any(x in title_lower for x in ['quiz', 'knowledge check', 'check your understanding']):
        return 'QUIZ'

    return 'CONTENT'


def extract_code_block(text: str) -> Optional[str]:
    """Extract the first code block from narration or visual description."""
    match = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def parse_metadata(content: str) -> LectureMetadata:
    """Extract lecture metadata from the header."""
    # Match "# Lecture N.N: Title" or "# Lecture N: Title"
    title_match = re.search(r'^#\s+Lecture\s+([\d.]+):\s+(.+)', content, re.MULTILINE)
    lecture_num = title_match.group(1).strip() if title_match else "0"
    title = title_match.group(2).strip() if title_match else "Untitled"

    section_match = re.search(r'\*\*Section\*\*:\s*(.+)', content)
    section = section_match.group(1).strip() if section_match else None

    duration_match = re.search(r'\*\*Duration\*\*:\s*(.+)', content)
    duration = duration_match.group(1).strip() if duration_match else None

    status_match = re.search(r'\*\*Status\*\*:\s*(.+)', content)
    status = status_match.group(1).strip() if status_match else None

    return LectureMetadata(
        lecture_number=lecture_num,
        title=title,
        section=section,
        duration=duration,
        status=status,
    )


def parse_slides(content: str) -> list:
    """Extract all slide sections from the markdown."""
    slides = []

    # Find all ## SLIDE N: Title sections
    slide_pattern = r'##\s+SLIDE\s+(\d+):\s+(.+?)(?=\n)(.*?)(?=\n##\s+SLIDE\s+\d+|\Z)'
    matches = re.findall(slide_pattern, content, re.DOTALL | re.IGNORECASE)

    for match in matches:
        slide_num = int(match[0])
        title = match[1].strip()
        slide_body = match[2]

        # Extract Visual description
        visual_match = re.search(r'\*\*Visual\*\*:\s*(.+?)(?=\n\n|\n\*\*|$)', slide_body, re.DOTALL)
        visual = visual_match.group(1).strip() if visual_match else ""

        # Remove the Visual line from body to get narration
        narration_body = re.sub(r'\*\*Visual\*\*:.*?(?=\n\n|\n\*\*)', '', slide_body, flags=re.DOTALL).strip()

        # Also remove exam tip structured fields if present
        narration_body = re.sub(r'\*\*Exam Trap\*\*:.*', '', narration_body, flags=re.DOTALL).strip()
        narration_body = re.sub(r'\*\*Correct Approach\*\*:.*', '', narration_body, flags=re.DOTALL).strip()

        # Extract code blocks before splitting on [click]
        code_block = extract_code_block(slide_body)

        # Split on [click] markers to get progressive reveal segments
        raw_segments = re.split(r'\[click\]', narration_body, flags=re.IGNORECASE)
        segments = []
        for i, seg in enumerate(raw_segments):
            seg_text = seg.strip()
            # Remove any remaining code fences for the narration text
            seg_text = re.sub(r'```[\w]*\n.*?```', '[CODE BLOCK]', seg_text, flags=re.DOTALL)
            if seg_text:
                segments.append({
                    'narration': seg_text,
                    'is_reveal': i > 0
                })

        has_clicks = len(raw_segments) > 1
        full_narration = '\n\n'.join(s['narration'] for s in segments)

        slide_type = determine_slide_type(title, visual, full_narration)

        slides.append({
            'slide_number': slide_num,
            'title': title,
            'slide_type': slide_type,
            'visual_description': visual,
            'segments': segments,
            'speaker_notes': full_narration,
            'has_clicks': has_clicks,
            'code_block': code_block,
        })

    return slides


def parse_lecture(markdown_path: str) -> dict:
    """Main function to parse a complete lecture markdown file."""
    content = Path(markdown_path).read_text(encoding='utf-8')

    metadata = parse_metadata(content)
    slides = parse_slides(content)

    return {
        'metadata': asdict(metadata),
        'slides': slides,
        'slide_count': len(slides),
    }


def main():
    parser = argparse.ArgumentParser(description='Parse Udemy lecture markdown into structured slide data')
    parser.add_argument('markdown_path', help='Path to the lecture markdown file')
    parser.add_argument('--output', '-o', help='Output JSON file path', default=None)

    args = parser.parse_args()

    md_path = Path(args.markdown_path)
    if not md_path.exists():
        print(f"Error: File not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing lecture: {md_path}")
    result = parse_lecture(str(md_path))

    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"JSON saved to: {output_path}")
    else:
        print(json.dumps(result, indent=2))

    print(f"\n--- Parse Summary ---")
    print(f"Lecture: {result['metadata']['lecture_number']} — {result['metadata']['title']}")
    print(f"Slides: {result['slide_count']}")
    for slide in result['slides']:
        clicks = " [clicks]" if slide['has_clicks'] else ""
        code = " [code]" if slide['code_block'] else ""
        print(f"  Slide {slide['slide_number']}: {slide['title']} [{slide['slide_type']}]{clicks}{code}")

    return result


if __name__ == '__main__':
    main()
