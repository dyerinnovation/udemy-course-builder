#!/usr/bin/env python3
"""Top-level orchestrator for the lecture video rendering pipeline.

Calls parse_lecture → tts_render → slides_export → mux in sequence.
Each stage is idempotent; assets that are already up-to-date are skipped
unless --force is passed.

Usage:
    python render.py --lecture 2.1 --course-root /path/to/course \
        --out artifacts/lectures/lecture-2.1.mp4

    # Partial renders
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --audio-only
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --slides-only
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --mux-only

    # Force full re-render
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --force
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add skill directory to path so sibling modules import cleanly
_SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SKILL_DIR))


def _verify_dependencies() -> None:
    """Check that required system tools are available. Hard-abort if any are missing."""
    import shutil
    missing = []
    for tool in ("ffmpeg", "ffprobe", "pdftoppm", "npx"):
        if shutil.which(tool) is None:
            missing.append(tool)
    if missing:
        sys.exit(
            f"ERROR: Required tool(s) not found on PATH: {', '.join(missing)}\n"
            "Install with:\n"
            "  brew install ffmpeg poppler node\n"
            "  (pdftoppm is part of the poppler package)"
        )


def _verify_env() -> None:
    """Verify that the .env file has ELEVENLABS_API_KEY set before any API calls."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        sys.exit("ERROR: python-dotenv not installed. Run: pip install python-dotenv")

    env_path = _SKILL_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    if not os.environ.get("ELEVENLABS_API_KEY", "").strip():
        sys.exit(
            f"ERROR: ELEVENLABS_API_KEY is not set.\n"
            f"Copy {_SKILL_DIR / '.env.example'} to {_SKILL_DIR / '.env'} "
            "and fill in your API key."
        )


def _validate_slide_counts(
    lecture_id: str,
    course_root: Path,
    parsed_slides: list[dict],
) -> None:
    """Validate that script SLIDE count == slidev slide count in the lecture range.

    Convention: there is no separate "synthesized cover" slide. Script SLIDE 1 plays
    directly over slidev's lecture-cover slide; SLIDE N plays over slidev slide N.
    See udemy-lecture-writer SKILL.md: "SLIDE 1 should be cover-flavored intro."

    Per-slide click counts are validated separately inside slides_export.py
    (by comparing slidev's --with-clicks frame count to script_click_counts[N]).
    """
    from slides_export import find_lecture_page_range
    section_num = int(lecture_id.split(".")[0])
    section_deck = course_root / "slidev" / f"section-{section_num}.md"

    if not section_deck.exists():
        print(
            f"WARN: Slidev deck {section_deck} not found; skipping slide-count validation.",
            file=sys.stderr,
        )
        return

    try:
        first_page, last_page = find_lecture_page_range(section_deck, lecture_id)
        slidev_count = last_page - first_page + 1
        script_count = len(parsed_slides)

        if slidev_count != script_count:
            sys.exit(
                f"ERROR: Slide count mismatch for lecture {lecture_id}.\n"
                f"  Script has {script_count} ## SLIDE sections\n"
                f"  Slidev deck has {slidev_count} slides in lecture range (pages {first_page}-{last_page})\n"
                "Fix by adding/removing a SLIDE in the script or a --- separator in the slidev deck.\n"
                "Note: SLIDE 1 narration plays over the slidev lecture-cover slide — no synthesized cover."
            )
        click_counts = [s["click_count"] for s in parsed_slides]
        print(
            f"[render] slide count validated: {script_count} script SLIDEs == {slidev_count} slidev slides "
            f"(per-slide [click] counts: {click_counts})",
            file=sys.stderr,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"WARN: Could not validate slide counts: {exc}", file=sys.stderr)


def render(
    lecture_id: str,
    course_root: Path,
    output: Path,
    audio_only: bool = False,
    slides_only: bool = False,
    mux_only: bool = False,
    force: bool = False,
) -> None:
    """Run the full or partial render pipeline."""
    from parse_lecture import parse_lecture
    from tts_render import render_tts
    from slides_export import export_slides
    from mux import mux as run_mux

    # Determine the temp assets directory
    assets_dir = output.parent / f".{output.stem}-assets"

    # Stage 0: preflight
    if not mux_only:
        _verify_dependencies()
    if not slides_only and not mux_only:
        _verify_env()

    # Stage 1: parse (always, to validate; also needed for slide-count check)
    print(f"[render] parsing lecture {lecture_id} ...", file=sys.stderr)
    parsed_slides = parse_lecture(lecture_id, course_root)
    print(
        f"[render] {len(parsed_slides)} slides in script",
        file=sys.stderr,
    )

    # Slide count validation (before any API calls)
    if not audio_only and not mux_only:
        _validate_slide_counts(lecture_id, course_root, parsed_slides)

    # Stage 2: TTS audio
    if not slides_only and not mux_only:
        print(f"[render] rendering TTS audio ...", file=sys.stderr)
        render_tts(
            lecture_id=lecture_id,
            course_root=course_root,
            out_dir=assets_dir,
            force=force,
        )
        if audio_only:
            print(f"[render] --audio-only: done. Assets in {assets_dir}", file=sys.stderr)
            return

    # Stage 3: slide export (passes per-slide script click counts so that
    # multi-click slides emit per-click frames matched to narration sub-chunks)
    if not audio_only and not mux_only:
        print(f"[render] exporting slides ...", file=sys.stderr)
        script_click_counts = [s["click_count"] for s in parsed_slides]
        export_slides(
            lecture_id=lecture_id,
            course_root=course_root,
            out_dir=assets_dir,
            force=force,
            script_click_counts=script_click_counts,
        )
        if slides_only:
            print(f"[render] --slides-only: done. Assets in {assets_dir}", file=sys.stderr)
            return

    # Stage 4: mux
    print(f"[render] muxing ...", file=sys.stderr)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_mux(
        assets_dir=assets_dir,
        output=output,
        force=force,
    )

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"[render] DONE: {output} ({size_mb:.1f} MB)", file=sys.stderr)
    print(str(output))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="render.py",
        description=(
            "Render a narrated lecture video (.mp4) from a lecture script + "
            "Slidev deck via ElevenLabs TTS + ffmpeg."
        ),
    )
    ap.add_argument("--lecture", required=True, help="Lecture ID, e.g. '2.1'")
    ap.add_argument(
        "--course-root",
        required=True,
        type=Path,
        help="Absolute path to the course repo root",
    )
    ap.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output path for the final lecture .mp4",
    )

    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--audio-only",
        action="store_true",
        help="Only render TTS audio (skip slide export and mux)",
    )
    mode.add_argument(
        "--slides-only",
        action="store_true",
        help="Only export slides to PNG (skip TTS and mux)",
    )
    mode.add_argument(
        "--mux-only",
        action="store_true",
        help="Only mux existing assets (skip TTS and slide export)",
    )

    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-render all stages, ignoring all cached assets",
    )

    args = ap.parse_args(argv)

    try:
        render(
            lecture_id=args.lecture,
            course_root=args.course_root.resolve(),
            output=args.out.resolve(),
            audio_only=args.audio_only,
            slides_only=args.slides_only,
            mux_only=args.mux_only,
            force=args.force,
        )
    except SystemExit:
        raise
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
