#!/usr/bin/env python3
"""Render per-slide TTS audio via ElevenLabs API.

For each slide in the parsed lecture, calls ElevenLabs text_to_speech.convert()
with locked voice settings and writes slide-NN.mp3. Idempotent: skips slides
whose .mp3 exists and is newer than the source script unless --force is set.

Pronunciation dictionary handling
---------------------------------

The skill ships a universal-tech-terms PLS at:
    <skill_dir>/pronunciation.template.pls

Each course MAY add course-specific entries at:
    <course_root>/course-metadata/pronunciation.pls

At render time, the two are merged (course entries win on grapheme
conflict), serialized to a combined PLS, and uploaded to ElevenLabs ONCE
per content hash. The returned pronunciation_dictionary_id + version_id are
cached at:
    <course_root>/course-metadata/tts-config.json

The cache is invalidated automatically when either PLS file changes (the
SHA-256 of the merged content is stored alongside the IDs). No env vars are
needed for the dictionary — it's fully auto-managed per course.

Usage:
    python tts_render.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets
    python tts_render.py --lecture 2.1 --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets --force
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Resolve .env from the skill directory (this file lives there)
_SKILL_DIR = Path(__file__).resolve().parent
_PLS_NS = "http://www.w3.org/2005/01/pronunciation-lexicon"
_PLS_NS_PREFIX = "{" + _PLS_NS + "}"


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
        load_dotenv()


def _require_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        sys.exit(
            f"ERROR: {key} is not set. "
            f"Add it to {_SKILL_DIR / '.env'} and retry. "
            f"See {_SKILL_DIR / 'voice-clone-setup.md'} for one-time setup."
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


# ---------------------------------------------------------------------------
# Pronunciation dictionary — auto-merge + auto-upload + per-course cache
# ---------------------------------------------------------------------------

def _parse_pls_lexemes(pls_path: Path) -> dict[str, str]:
    """Parse a PLS file. Returns {grapheme: alias_text} dict.

    Reads `<alias>` rules (literal text substitution). `<phoneme>` rules are
    INTENTIONALLY IGNORED — they don't work on `eleven_multilingual_v2`
    (the model this skill uses). See playbook.md
    "ElevenLabs pronunciation rule types — alias vs phoneme model support"
    for the full explanation.

    Raises ValueError on malformed XML. Returns empty dict if file missing.
    """
    if not pls_path.exists():
        return {}
    ET.register_namespace("", _PLS_NS)
    try:
        tree = ET.parse(pls_path)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid PLS XML at {pls_path}: {exc}") from exc

    root = tree.getroot()
    entries: dict[str, str] = {}
    skipped_phoneme = 0
    for lexeme in root.iter(_PLS_NS_PREFIX + "lexeme"):
        grapheme_el = lexeme.find(_PLS_NS_PREFIX + "grapheme")
        alias_el = lexeme.find(_PLS_NS_PREFIX + "alias")
        phoneme_el = lexeme.find(_PLS_NS_PREFIX + "phoneme")
        if grapheme_el is None:
            continue
        grapheme = (grapheme_el.text or "").strip()
        if not grapheme:
            continue
        if alias_el is not None and (alias_el.text or "").strip():
            entries[grapheme] = (alias_el.text or "").strip()
        elif phoneme_el is not None:
            # Skip phoneme-only entries with a warning rather than silently
            # producing a dictionary the model ignores.
            skipped_phoneme += 1
    if skipped_phoneme:
        import sys as _sys
        print(
            f"WARN: {pls_path.name} contains {skipped_phoneme} phoneme-only entries — "
            f"these are SILENTLY IGNORED by eleven_multilingual_v2. Convert to "
            f"<alias> text-substitution rules to apply them. See playbook.md.",
            file=_sys.stderr,
        )
    return entries


def _build_merged_pls(entries: dict[str, str]) -> str:
    """Build a PLS 1.0 XML string from a {grapheme: alias_text} dict.

    Emits `<alias>` rules (NOT `<phoneme>` rules) so the dictionary actually
    affects `eleven_multilingual_v2` output. See playbook.md
    "ElevenLabs pronunciation rule types — alias vs phoneme model support".

    Entries are sorted by grapheme for deterministic SHA-256 hashing —
    different machines / runs produce byte-identical output for the same
    input, so cache invalidation is reliable.
    """
    # ElevenLabs's PLS parser is strict about whitespace in attribute
    # declarations — multi-line attributes on <lexicon> trigger a 400
    # "Lexicon file formatted incorrectly" even though the XML is valid.
    # Keep <lexicon> opening tag on a single line.
    # See playbook.md "ElevenLabs PLS upload — two undocumented format quirks"
    # for the full bug write-up + verification command.
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<lexicon version="1.0" xmlns="http://www.w3.org/2005/01/pronunciation-lexicon" xml:lang="en-US">',
    ]
    for grapheme in sorted(entries.keys()):
        alias_text = entries[grapheme]
        g_esc = (
            grapheme.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        a_esc = (
            alias_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        lines.append("  <lexeme>")
        lines.append(f"    <grapheme>{g_esc}</grapheme>")
        lines.append(f"    <alias>{a_esc}</alias>")
        lines.append("  </lexeme>")
    lines.append("</lexicon>")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def _resolve_pronunciation_dict(course_root: Path, api_key: str) -> tuple[str, str] | None:
    """Merge skill template + course override, upload if changed, return (id, version_id).

    Returns None if the merged PLS has zero lexemes (no dict to apply).

    Cache layout in <course_root>/course-metadata/tts-config.json:
        {
          "pronunciation_dict": {
            "id": "...",
            "version_id": "...",
            "pls_sha256": "abc...",
            "uploaded_at": "2026-05-14T10:23:45+00:00",
            "entry_count": 19
          }
        }
    """
    template_path = _SKILL_DIR / "pronunciation.template.pls"
    course_pls_path = course_root / "course-metadata" / "pronunciation.pls"
    cache_path = course_root / "course-metadata" / "tts-config.json"

    # 1. Merge skill template + course override
    template_entries = _parse_pls_lexemes(template_path)
    course_entries = _parse_pls_lexemes(course_pls_path)
    merged = {**template_entries, **course_entries}  # course wins on conflict

    if not merged:
        print(
            "[pron] no PLS entries found in skill template or course override; "
            "rendering without pronunciation dictionary.",
            file=sys.stderr,
        )
        return None

    # 2. Serialize merged PLS deterministically + hash
    merged_pls = _build_merged_pls(merged)
    merged_sha = hashlib.sha256(merged_pls.encode("utf-8")).hexdigest()

    # 3. Check cache
    cached: dict = {}
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
    cached_dict = cached.get("pronunciation_dict", {})
    if (
        cached_dict.get("pls_sha256") == merged_sha
        and cached_dict.get("id")
        and cached_dict.get("version_id")
    ):
        print(
            f"[pron] using cached dictionary {cached_dict['id'][:12]}... "
            f"({len(merged)} entries, sha256 {merged_sha[:8]})",
            file=sys.stderr,
        )
        return cached_dict["id"], cached_dict["version_id"]

    # 4. Cache miss — upload merged PLS to ElevenLabs
    print(
        f"[pron] uploading merged dictionary ({len(merged)} entries: "
        f"{len(template_entries)} skill + {len(course_entries)} course override) ...",
        file=sys.stderr,
    )
    # Write merged PLS to a temp file for multipart upload
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pls", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(merged_pls)
        tmp_path = Path(tmp.name)

    try:
        course_slug = course_root.name
        dict_name = f"{course_slug} — auto-merged"
        import httpx
        with open(tmp_path, "rb") as fh:
            # Note: ElevenLabs's PLS parser rejects `application/pls+xml` content-type
            # uploads even when the XML is valid. Use `text/xml` instead (empirically
            # confirmed to work via curl tests against the same endpoint).
            # See playbook.md "ElevenLabs PLS upload — two undocumented format quirks"
            # for the full bug write-up + verification command.
            response = httpx.post(
                "https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file",
                headers={"xi-api-key": api_key},
                files={
                    "file": ("pronunciation.pls", fh, "text/xml"),
                },
                data={"name": dict_name},
                timeout=60.0,
            )
        if response.status_code >= 400:
            sys.exit(
                f"ERROR: pronunciation dictionary upload failed "
                f"(status {response.status_code}): {response.text}"
            )
        body = response.json()
    finally:
        tmp_path.unlink(missing_ok=True)

    dict_id = body.get("id") or body.get("pronunciation_dictionary_id") or ""
    version_id = body.get("version_id") or ""
    if not dict_id or not version_id:
        sys.exit(
            f"ERROR: upload response missing id/version_id: {body!r}"
        )

    # 5. Write back to cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cached["pronunciation_dict"] = {
        "id": dict_id,
        "version_id": version_id,
        "pls_sha256": merged_sha,
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "entry_count": len(merged),
    }
    cache_path.write_text(
        json.dumps(cached, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"[pron] uploaded dictionary {dict_id[:12]}... cached in "
        f"{cache_path.relative_to(course_root)}",
        file=sys.stderr,
    )
    return dict_id, version_id


# ---------------------------------------------------------------------------
# Silence placeholder
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_tts(
    lecture_id: str,
    course_root: Path,
    out_dir: Path,
    force: bool = False,
) -> list[Path]:
    """Render per-sub-chunk TTS audio for all slides of a lecture.

    Output naming (aligned with slides_export.py):
        slide-NN-cM.mp3   NN = slide index (1-padded), M = click state (0..N_clicks)

    Script SLIDE 1's narration plays over the slidev cover; we do NOT
    synthesize a separate cover narration. (See lecture-writer SKILL.md
    convention: SLIDE 1 should be cover-flavored intro.)

    Returns list of written .mp3 paths in (slide, click) order.
    """
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

    out_dir.mkdir(parents=True, exist_ok=True)

    slides = parse_lecture(lecture_id, course_root)
    lecture_path = find_lecture_file(lecture_id, course_root)
    script_mtime = lecture_path.stat().st_mtime

    # Auto-resolve pronunciation dictionary (skill template + course override)
    pron_dict = _resolve_pronunciation_dict(course_root, api_key)

    client = ElevenLabs(api_key=api_key)

    voice_settings = VoiceSettings(
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=True,
    )

    pron_kwargs: dict = {}
    if pron_dict is not None:
        dict_id, dict_version = pron_dict
        try:
            from elevenlabs.types import PronunciationDictionaryVersionLocator
            pron_kwargs["pronunciation_dictionary_locators"] = [
                PronunciationDictionaryVersionLocator(
                    pronunciation_dictionary_id=dict_id,
                    version_id=dict_version,
                )
            ]
        except ImportError:
            print(
                "WARN: PronunciationDictionaryVersionLocator not found in SDK; "
                "skipping dictionary. Upgrade: pip install --upgrade elevenlabs",
                file=sys.stderr,
            )

    written: list[Path] = []

    # Emit one MP3 per narration sub-chunk so each plays over its corresponding
    # click-state PNG (produced by playwright_capture.py). Naming is aligned:
    # slide-NN-cM.mp3 pairs with slide-NN-cM.png (mux.py sorts by (NN, M)).
    for slide in slides:
        slide_n = slide["slide_n"]
        narrations = slide.get("narrations") or [slide.get("narration_text", "")]

        for m_idx, narration in enumerate(narrations):
            mp3_path = out_dir / f"slide-{slide_n:02d}-c{m_idx}.mp3"

            if (
                not force
                and mp3_path.exists()
                and mp3_path.stat().st_size > 0
                and mp3_path.stat().st_mtime > script_mtime
            ):
                duration = _ffprobe_duration(mp3_path)
                print(
                    f"[tts] slide-{slide_n:02d}-c{m_idx}.mp3  skipped (cached, {duration:.1f}s)",
                    file=sys.stderr,
                )
                written.append(mp3_path)
                continue

            if not narration.strip():
                print(
                    f"[tts] slide-{slide_n:02d}-c{m_idx}.mp3  WARN: empty narration; writing silence placeholder",
                    file=sys.stderr,
                )
                _write_silence(mp3_path)
                written.append(mp3_path)
                continue

            sub_label = f" (sub-chunk {m_idx + 1}/{len(narrations)})" if len(narrations) > 1 else ""
            print(
                f"[tts] slide-{slide_n:02d}-c{m_idx}.mp3  rendering{sub_label}...",
                file=sys.stderr,
                end="",
                flush=True,
            )

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
