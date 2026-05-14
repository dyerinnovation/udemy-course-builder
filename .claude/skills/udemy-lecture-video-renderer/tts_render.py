#!/usr/bin/env python3
"""Render per-slide TTS audio via ElevenLabs API.

For each slide in the parsed lecture, calls ElevenLabs text_to_speech.convert()
with locked voice settings and writes slide-NN.mp3. Idempotent: skips slides
whose .mp3 exists and is newer than the source script unless --force is set.

Usage:
    python tts_render.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets
    python tts_render.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets --force
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Resolve .env from the skill directory (this file lives there)
_SKILL_DIR = Path(__file__).resolve().parent


def _load_env() -> None:
    """Load .env from the skill directory via python-dotenv."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        sys.exit(
            "ERROR: python-dotenv is not installed. "
            "Run: pip install python-dotenv"
        )
    env_path = _SKILL_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Attempt to load from CWD as fallback
        load_dotenv()


def _require_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        sys.exit(
            f"ERROR: {key} is not set. "
            f"Add it to {_SKILL_DIR / '.env'} and retry."
        )
    return val


def _ffprobe_duration(mp3_path: Path) -> float:
    """Return duration in seconds via ffprobe, or -1.0 on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return -1.0


def _synthesize_cover_narration(lecture_id: str, lecture_title: str) -> str:
    """Generate cover slide narration from the lecture title.

    If the title contains an em-dash (or regular dash), use the part after it
    as the subtitle. Otherwise use the full title.
    """
    # Try to extract subtitle after em-dash or colon
    for sep in [" — ", " - ", ": "]:
        if sep in lecture_title:
            parts = lecture_title.split(sep, 1)
            subtitle = parts[1].strip()
            return f"Lecture {lecture_id}: {subtitle}."
    return f"Lecture {lecture_id}: {lecture_title}."


def render_tts(
    lecture_id: str,
    course_root: Path,
    out_dir: Path,
    force: bool = False,
) -> list[Path]:
    """Render TTS audio for all slides of a lecture.

    Returns list of written .mp3 paths (in slide order, including cover).
    """
    # Import parse_lecture from the same skill directory
    sys.path.insert(0, str(_SKILL_DIR))
    from parse_lecture import find_lecture_file, parse_lecture

    try:
        from elevenlabs import ElevenLabs, VoiceSettings
    except ImportError:
        sys.exit(
            "ERROR: elevenlabs SDK not installed. "
            "Run: pip install 'elevenlabs>=1.0'"
        )

    _load_env()
    api_key = _require_env("ELEVENLABS_API_KEY")
    voice_id = _require_env("ELEVENLABS_VOICE_ID")
    dict_id = os.environ.get("ELEVENLABS_PRONUNCIATION_DICT_ID", "").strip()
    dict_version = os.environ.get("ELEVENLABS_PRONUNCIATION_DICT_VERSION", "").strip()

    out_dir.mkdir(parents=True, exist_ok=True)

    # Parse the lecture script
    slides = parse_lecture(lecture_id, course_root)
    lecture_path = find_lecture_file(lecture_id, course_root)
    script_mtime = lecture_path.stat().st_mtime

    # Determine if we need a synthesized cover slide
    # The Slidev deck has N+1 slides (cover + body). Parse the LECTURE marker
    # from the Slidev deck to get the title for cover narration.
    section_num = int(lecture_id.split(".")[0])
    section_deck = course_root / "slidev" / f"section-{section_num}.md"
    cover_narration = _get_cover_narration(lecture_id, section_deck)

    client = ElevenLabs(api_key=api_key)

    voice_settings = VoiceSettings(
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=True,
    )

    # Build pronunciation_dictionary_locators kwarg conditionally
    pron_kwargs: dict = {}
    if dict_id and dict_version:
        try:
            from elevenlabs.types import PronunciationDictionaryVersionLocator
            pron_kwargs["pronunciation_dictionary_locators"] = [
                PronunciationDictionaryVersionLocator(
                    pronunciation_dictionary_id=dict_id,
                    version_id=dict_version,
                )
            ]
        except ImportError:
            # Older SDK versions may not have this type — skip gracefully
            print(
                "WARN: PronunciationDictionaryVersionLocator not found in SDK; "
                "skipping pronunciation dictionary. Upgrade with: pip install --upgrade elevenlabs",
                file=sys.stderr,
            )

    written: list[Path] = []

    # Build the full slide list: cover (01) + body slides (02..N+1)
    all_slides: list[tuple[int, str]] = []  # (output_slide_n, narration_text)

    # Slide 01 = Cover
    all_slides.append((1, cover_narration))
    # Body slides: script slide 1 → output slide 02, etc.
    for slide in slides:
        all_slides.append((slide["slide_n"] + 1, slide["narration_text"]))

    for output_n, narration in all_slides:
        mp3_path = out_dir / f"slide-{output_n:02d}.mp3"

        # Idempotency check
        if (
            not force
            and mp3_path.exists()
            and mp3_path.stat().st_size > 0
            and mp3_path.stat().st_mtime > script_mtime
        ):
            duration = _ffprobe_duration(mp3_path)
            print(
                f"[tts] slide-{output_n:02d}.mp3  skipped (cached, {duration:.1f}s)",
                file=sys.stderr,
            )
            written.append(mp3_path)
            continue

        if not narration.strip():
            print(
                f"[tts] slide-{output_n:02d}.mp3  WARN: empty narration, writing silence placeholder",
                file=sys.stderr,
            )
            # Write a brief silence placeholder so mux doesn't fail
            _write_silence(mp3_path)
            written.append(mp3_path)
            continue

        print(f"[tts] slide-{output_n:02d}.mp3  rendering...", file=sys.stderr, end="", flush=True)

        audio_stream = client.text_to_speech.convert(
            voice_id=voice_id,
            text=narration,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            voice_settings=voice_settings,
            **pron_kwargs,
        )

        with open(mp3_path, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)

        duration = _ffprobe_duration(mp3_path)
        size_kb = mp3_path.stat().st_size // 1024
        print(f" {duration:.1f}s ({size_kb} KB)", file=sys.stderr)
        written.append(mp3_path)

    return written


def _write_silence(path: Path) -> None:
    """Write a 1-second silent MP3 via ffmpeg as a placeholder."""
    subprocess.run(
        [
            "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "1", "-q:a", "9", "-acodec", "libmp3lame",
            "-y", str(path),
        ],
        capture_output=True,
        check=False,
    )


def _get_cover_narration(lecture_id: str, section_deck: Path) -> str:
    """Extract the LECTURE marker title from the Slidev deck for cover narration."""
    if not section_deck.exists():
        return f"Lecture {lecture_id}."

    import re
    lecture_marker_re = re.compile(
        rf"<!--\s+LECTURE\s+{re.escape(lecture_id)}\s+[—\-–]\s+(.+?)\s*-->",
        re.IGNORECASE,
    )
    text = section_deck.read_text(encoding="utf-8")
    match = lecture_marker_re.search(text)
    if match:
        title = match.group(1).strip()
        return _synthesize_cover_narration(lecture_id, title)
    return f"Lecture {lecture_id}."


def _synthesize_cover_narration(lecture_id: str, lecture_title: str) -> str:
    """Generate cover narration from the lecture title."""
    for sep in [" — ", " - ", ": "]:
        if sep in lecture_title:
            parts = lecture_title.split(sep, 1)
            subtitle = parts[1].strip()
            return f"Lecture {lecture_id}: {subtitle}."
    return f"Lecture {lecture_id}: {lecture_title}."


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tts_render.py",
        description="Render per-slide TTS audio via ElevenLabs API.",
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
        help="Directory to write slide-NN.mp3 files",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-render all slides, ignoring cache",
    )
    args = ap.parse_args(argv)

    try:
        written = render_tts(
            lecture_id=args.lecture,
            course_root=args.course_root,
            out_dir=args.out_dir,
            force=args.force,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"[tts] {len(written)} audio file(s) ready in {args.out_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
