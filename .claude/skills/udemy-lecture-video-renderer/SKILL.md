---
name: udemy-lecture-video-renderer
description: >
  Render an end-to-end narrated lecture video (.mp4) from a lecture script +
  matching Slidev section deck via ElevenLabs TTS (cloned voice) + ffmpeg
  muxing. Parses lecture .md scripts into per-slide narration chunks, calls
  ElevenLabs text-to-speech with locked voice settings, exports the Slidev
  section deck to PNG slides via pdftoppm, then muxes each PNG + MP3 pair
  into a segment MP4 and concatenates them into a final lecture video.
  Supports per-lecture smoke tests, idempotent re-runs (per-asset mtime
  checks skip unchanged files), and partial re-renders via --audio-only,
  --slides-only, or --mux-only flags. Reads ELEVENLABS_API_KEY,
  ELEVENLABS_VOICE_ID, ELEVENLABS_PRONUNCIATION_DICT_ID, and
  ELEVENLABS_PRONUNCIATION_DICT_VERSION from a .env file in the skill
  directory. Requires ffmpeg, ffprobe, pdftoppm (poppler-utils), and Node.js
  (for npx slidev export). Hard-aborts on missing API key, failed Slidev
  export, or slide-count mismatch — no silent degradation.
allowed-tools: "Read, Glob, Grep, Bash, Edit, Write"
---

# Udemy Lecture Video Renderer

## Overview

Converts a lecture script (`.md`) + its Slidev section deck into a final
narrated MP4 lecture video. The pipeline runs in four idempotent stages:

```
lecture script .md ─┐                         ┌─► per-slide .mp3 (ElevenLabs TTS)
                    ├──parse_lecture.py──────►│
slidev section-N.md ┘                         └─► per-slide .png (slidev → pdftoppm)
                                                          │
                                                          ▼
                                                 ffmpeg mux PNG + MP3 → segment .mp4
                                                          │
                                                          ▼
                                                 ffmpeg concat → lecture-X.Y.mp4
```

Each stage is independently re-runnable. Assets that already exist and are
newer than the source script are skipped unless `--force` is passed.

## Environment contract

The following environment variables must be set in `.env` (in the skill
directory):

| Variable | Required | Notes |
|---|---|---|
| `ELEVENLABS_API_KEY` | YES | ElevenLabs API key. Hard-abort if missing. |
| `ELEVENLABS_VOICE_ID` | YES | Voice ID of the cloned narration voice. |
| `ELEVENLABS_PRONUNCIATION_DICT_ID` | NO | Pronunciation dictionary ID uploaded via PLS lexicon. Omit kwarg if unset. |
| `ELEVENLABS_PRONUNCIATION_DICT_VERSION` | NO | Version string for the dictionary. Required if DICT_ID is set. |

Copy `.env.example` to `.env` and fill in the values before running. The
`.env` file is gitignored. Do NOT commit it.

## Prerequisites

- **Python 3.10+** with packages from `requirements.txt` installed:
  `pip install -r requirements.txt`
- **ffmpeg** and **ffprobe** on PATH (Homebrew: `brew install ffmpeg`)
- **pdftoppm** on PATH (Homebrew: `brew install poppler`)
- **Node.js + npx** on PATH (for `npx slidev export`)
- A valid ElevenLabs account with a cloned voice and API key in `.env`
- The Slidev section deck at `<course_root>/slidev/section-N.md` (N = section
  number parsed from the lecture ID)

## When to use

- Recording narrated lecture videos from finished lecture scripts + Slidev decks
  without a recording booth or on-camera session.
- Smoke-testing a single lecture (e.g., `--lecture 2.1`) before scaling to all
  94 lectures.
- Partial re-renders: re-doing just the audio (`--audio-only`), just the slides
  (`--slides-only`), or just the mux (`--mux-only`) after fixing one layer.

## When NOT to use

- **Uploading the final MP4 to Udemy** — use `udemy-curriculum-populator` first
  to create lecture stubs, then upload via the Udemy dashboard manually or via a
  future `udemy-video-uploader` skill.
- **Producing slides** — the Slidev deck must already exist. Use
  `udemy-slide-creator` to author it first.
- **Writing lecture scripts** — use `udemy-lecture-writer`.

## Invocation

### Full render (smoke test for lecture 2.1)

```bash
python /path/to/udemy-lecture-video-renderer/render.py \
  --lecture 2.1 \
  --course-root /path/to/claude-architect-udemy-course \
  --out artifacts/lectures/lecture-2.1.mp4
```

### Partial renders

```bash
# Regenerate audio only (e.g. after tuning voice settings)
python render.py --lecture 2.1 --course-root . --out artifacts/lectures/lecture-2.1.mp4 --audio-only

# Regenerate slides only (e.g. after updating the Slidev deck)
python render.py --lecture 2.1 --course-root . --out artifacts/lectures/lecture-2.1.mp4 --slides-only

# Re-mux from existing assets (fastest — no API calls, no slidev export)
python render.py --lecture 2.1 --course-root . --out artifacts/lectures/lecture-2.1.mp4 --mux-only

# Force full re-render (ignore all cached assets)
python render.py --lecture 2.1 --course-root . --out artifacts/lectures/lecture-2.1.mp4 --force
```

### Per-module CLIs (for debugging individual stages)

```bash
# Inspect parsed narration for a lecture (prints JSON to stdout)
python parse_lecture.py --lecture 2.1 --course-root /path/to/course

# Render TTS audio for all slides of a lecture (reads .env from skill dir)
python tts_render.py --lecture 2.1 --course-root /path/to/course \
  --out-dir /tmp/lecture-2.1-assets

# Export Slidev slides for a lecture (produces per-slide PNGs)
python slides_export.py --lecture 2.1 --course-root /path/to/course \
  --out-dir /tmp/lecture-2.1-assets

# Mux assets from a directory into a final MP4
python mux.py --assets-dir /tmp/lecture-2.1-assets --output lecture-2.1.mp4
```

## Script format contract

Lecture scripts are expected at:
`<course_root>/scripts/section-NN-<slug>/X.Y-<title>.md`

Each script must have `## SLIDE N: Title` headings (one per slide). The
heading line itself is not narrated. Lines starting with `**Visual**:` and
`**Camera direction**:` are stripped. Fenced code blocks are stripped (code
on screen, not read aloud). `[click]` markers become `<break time="0.8s" />`
SSML pauses in the TTS payload.

## Slide-offset rule

Slidev decks prepend a Cover slide before SLIDE 1 of the script. If the
script has N slides, the Slidev deck for that lecture has N+1 slides. The
parser auto-synthesizes cover narration from the `<!-- LECTURE X.Y — Title -->`
marker: `"Lecture {X.Y}: {Title}."`. The render aborts with a clear error if
the slide counts don't satisfy this N+1 relationship.

## TTS settings (locked)

These settings are hardcoded in `tts_render.py` and must not be changed
without re-running a smoke test:

- `model_id`: `eleven_multilingual_v2`
- `output_format`: `mp3_44100_128`
- `stability`: `0.5`
- `similarity_boost`: `0.75`
- `style`: `0.0`
- `use_speaker_boost`: `True`

## ffmpeg encoding (locked)

Per-slide segment:
```bash
ffmpeg -loop 1 -i slide-NN.png -i slide-NN.mp3 \
  -c:v libx264 -tune stillimage -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
  segment-NN.mp4
```

Final concat:
```bash
ffmpeg -f concat -safe 0 -i concat-list.txt -c copy lecture-X.Y.mp4
```

## Pronunciation dictionary

Upload `pronunciation.pls` once to ElevenLabs:

```bash
curl -X POST https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -F "file=@pronunciation.pls;type=application/pls+xml" \
  -F "name=CCA Course Lexicon"
```

Capture the returned `pronunciation_dictionary_id` and `version_id` into `.env`.

## Related skills

- `udemy-lecture-writer` — writes the lecture scripts this skill consumes.
- `udemy-slide-creator` — produces the Slidev decks this skill exports.
- `slidev-runner` — dev/build/scope-fix for Slidev decks.
- `udemy-study-guide-renderer` — sibling Python-based renderer (PDF, not MP4).
