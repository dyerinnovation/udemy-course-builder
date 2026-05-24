#!/usr/bin/env python3
"""Top-level orchestrator for the lecture video rendering pipeline.

Calls parse_lecture → tts_render → slides_export → mux in sequence.
After a successful mux, also writes the per-lecture feedback HTML page
(<course_root>/feedback/lecture-X.Y/index.html) so the user can capture
review notes per slide and export a JSON bundle for the iteration loop.

Each stage is idempotent; assets that are already up-to-date are skipped
unless --force is passed.

Usage:
    python render.py --lecture 2.1 --course-root /path/to/course \
        --out artifacts/lectures/lecture-2.1.mp4

    # Partial renders
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --audio-only
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --slides-only
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --mux-only

    # Regenerate ONLY the feedback HTML (no audio/video/slide re-render)
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --feedback-only

    # Force full re-render
    python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --force

    # Write to an external lecture-output-root (per-section subdirs auto-derived)
    # --lecture-output-root takes precedence over --out. The resulting MP4 lands at:
    #   <lecture_output_root>/section-<N>/lecture-<X.Y>.mp4
    # The assets dir is colocated (sibling .lecture-<X.Y>-assets/ under that section dir).
    python render.py --lecture 2.2 --course-root . \
        --lecture-output-root /Volumes/Dev_SSD/.../Claude-Architect-Course/lectures
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


def _prune_orphan_assets(parsed_slides: list[dict], assets_dir: Path) -> int:
    """Delete per-click asset files whose chunk index exceeds the current
    script's click_count for that slide. Returns the count deleted.

    Fixes the historical --force orphan-asset bug: if a slide previously had
    5 chunks and the script now declares 3, the old slide-NN-c3.* / c4.*
    files persist and get picked up by mux's slide-NN-c*.* glob, producing
    a broken MP4 with stale audio/visual paired into mismatched segments
    (or extra silent tail segments at slide end).

    Pure-static slides (script_click_count == 0) keep only slide-NN-c0.*
    files; any cN where N > 0 is an orphan from a prior chunked render.

    Safe to run on every render — files matching the current click_count
    are left intact, so this composes correctly with the per-asset mtime
    cache that skips up-to-date files.
    """
    import re as _re
    if not assets_dir.exists():
        return 0
    # max valid chunk index per slide = click_count
    max_chunk_per_slide = {s["slide_n"]: s["click_count"] for s in parsed_slides}
    rx = _re.compile(r"^(?:slide|segment)-(\d+)-c(\d+)\.(?:png|mp3|mp4)$")
    deleted = 0
    for f in assets_dir.iterdir():
        if not f.is_file():
            continue
        m = rx.match(f.name)
        if not m:
            continue
        slide_n, chunk_n = int(m.group(1)), int(m.group(2))
        if slide_n not in max_chunk_per_slide:
            # Whole slide removed from the script — orphan slide. Delete.
            f.unlink()
            deleted += 1
            continue
        if chunk_n > max_chunk_per_slide[slide_n]:
            f.unlink()
            deleted += 1
    if deleted:
        print(
            f"[render] pruned {deleted} orphan per-click asset(s) from "
            f"{assets_dir.name}/ (chunking shrank since prior render)",
            file=sys.stderr,
        )
    return deleted


def _generate_feedback_html_safe(
    lecture_id: str, course_root: Path, assets_dir: Path
) -> None:
    """Write the per-lecture feedback HTML. Never raises — feedback HTML is a
    convenience, not a hard requirement. Logs a warning if it can't be built.
    """
    try:
        from generate_feedback_html import generate_feedback_html
        out_html = generate_feedback_html(
            lecture_id=lecture_id,
            course_root=course_root,
            assets_dir=assets_dir,
        )
        print(f"[render] feedback HTML: {out_html}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — intentionally broad
        print(
            f"[render] WARN: feedback HTML generation failed ({type(exc).__name__}: {exc}). "
            f"Continuing — MP4 is fine. Re-run with --feedback-only after fixing.",
            file=sys.stderr,
        )


def render(
    lecture_id: str,
    course_root: Path,
    output: Path,
    audio_only: bool = False,
    slides_only: bool = False,
    mux_only: bool = False,
    feedback_only: bool = False,
    force: bool = False,
) -> None:
    """Run the full or partial render pipeline."""
    from parse_lecture import parse_lecture
    from tts_render import render_tts
    from slides_export import export_slides
    from mux import mux as run_mux

    # Determine the temp assets directory
    assets_dir = output.parent / f".{output.stem}-assets"

    # --feedback-only: skip everything else; just (re)generate the HTML
    if feedback_only:
        print(f"[render] --feedback-only: regenerating HTML for lecture {lecture_id}",
              file=sys.stderr)
        _generate_feedback_html_safe(lecture_id, course_root, assets_dir)
        return

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

    # Stage 1b: prune orphan per-click assets from prior runs whose chunking
    # has since shrunk. Must run BEFORE any stage so mtime-based caching in
    # tts_render and slides_export still works for assets that ARE valid.
    # See _prune_orphan_assets docstring for the historical bug this fixes.
    if not mux_only:
        _prune_orphan_assets(parsed_slides, assets_dir)

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
            # Slides exist — generate the feedback HTML so the user can preview
            # thumbnails even before the audio/mux finishes.
            _generate_feedback_html_safe(lecture_id, course_root, assets_dir)
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

    # Stage 5: feedback HTML (refresh on every full render — matches the
    # "refresh the HTML after every build" convention from the scale-up plan)
    _generate_feedback_html_safe(lecture_id, course_root, assets_dir)

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
        required=False,
        type=Path,
        default=None,
        help=(
            "Output path for the final lecture .mp4. Optional if "
            "--lecture-output-root is provided. Mutually exclusive with "
            "--lecture-output-root."
        ),
    )
    ap.add_argument(
        "--lecture-output-root",
        required=False,
        type=Path,
        default=None,
        help=(
            "External lectures root (e.g. a shared SSD). When set, the output "
            "MP4 path is auto-derived as "
            "<lecture_output_root>/section-<N>/lecture-<X.Y>.mp4 "
            "and the per-asset directory is colocated alongside it. "
            "Used to keep large media off the course repo. Aborts with an "
            "actionable error if the root path doesn't exist (e.g. SSD not "
            "mounted) rather than silently writing into a stale mountpoint."
        ),
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
    mode.add_argument(
        "--feedback-only",
        action="store_true",
        help=(
            "Only regenerate the per-lecture feedback HTML page from the "
            "existing assets directory. No audio/video/slide re-render. "
            "Use this when iterating on the HTML template itself."
        ),
    )

    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-render all stages, ignoring all cached assets",
    )

    args = ap.parse_args(argv)

    # Resolve --out, possibly derived from --lecture-output-root.
    if args.out is not None and args.lecture_output_root is not None:
        sys.exit(
            "ERROR: pass --out OR --lecture-output-root, not both. "
            "When --lecture-output-root is set, --out is auto-derived."
        )
    if args.out is None and args.lecture_output_root is None:
        sys.exit(
            "ERROR: must pass either --out or --lecture-output-root."
        )

    if args.lecture_output_root is not None:
        # Pre-flight: the configured root must exist. Aborting here is
        # MUCH better than silently writing into a non-mounted /Volumes
        # placeholder (which macOS lets you do, then your render appears
        # to "succeed" but the file is invisible once the volume mounts).
        root = args.lecture_output_root.resolve()
        if not root.exists():
            sys.exit(
                f"ERROR: --lecture-output-root {root!s} does not exist.\n"
                "If this is an external drive (e.g. /Volumes/Dev_SSD/...), "
                "mount it before running render.\n"
                "Or pass --out <local-path> to fall back to a local output."
            )
        if not root.is_dir():
            sys.exit(
                f"ERROR: --lecture-output-root {root!s} exists but is not a directory."
            )
        try:
            section_num = int(args.lecture.split(".", 1)[0])
        except (ValueError, IndexError):
            sys.exit(f"ERROR: cannot derive section number from --lecture {args.lecture!r}")
        section_dir = root / f"section-{section_num}"
        # Create the section subdir up-front so output.parent.mkdir later succeeds.
        section_dir.mkdir(parents=True, exist_ok=True)
        args.out = section_dir / f"lecture-{args.lecture}.mp4"

    try:
        render(
            lecture_id=args.lecture,
            course_root=args.course_root.resolve(),
            output=args.out.resolve(),
            audio_only=args.audio_only,
            slides_only=args.slides_only,
            mux_only=args.mux_only,
            feedback_only=args.feedback_only,
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
