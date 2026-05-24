---
name: udemy-lecture-video-renderer
description: >
  Render an end-to-end narrated lecture video (.mp4) from a lecture script +
  matching Slidev section deck via ElevenLabs TTS (cloned voice) + ffmpeg
  muxing. Course-agnostic — works for any Udemy course that follows the
  plugin's script + Slidev conventions. Click-aware: each [click] marker in
  the script narration aligns 1:1 with a slidev click reveal on the matching
  slide; the renderer drives a headless Chromium (Playwright) against the
  running Slidev dev server to capture per-click PNG frames, then emits
  per-sub-chunk MP3 audio, then muxes them in (slide, click) order — so the
  final video shows code/content visually unfolding in chunks at the pace of
  the narration. Slides with zero [click] markers in the script render as a
  single final-state frame regardless of slidev clicks. Pure-static lectures
  skip Playwright and fall back to slidev's static PDF export path. The cloned voice + API key are
  configured ONCE per user (in the skill's .env); each course can supply
  its own pronunciation overrides at course-metadata/pronunciation.pls,
  which the skill auto-merges with a universal tech-term template,
  uploads to ElevenLabs, and caches per-course at
  course-metadata/tts-config.json (SHA-256 invalidated when the PLS
  changes). Supports per-lecture smoke tests, idempotent re-runs (per-asset
  mtime checks skip unchanged files), and partial re-renders via
  --audio-only, --slides-only, or --mux-only flags. After a successful render,
  also auto-generates a per-lecture Dyer-Innovation-branded feedback HTML page
  (with slide thumbnails, text inputs, paste/drop image attachments, IndexedDB
  autosave) at <course_root>/feedback/lecture-X.Y/index.html that the user
  opens in a browser to capture review notes — export produces a JSON bundle
  that unpack_feedback.py turns into the round-N markdown feedback files the
  iteration loop consumes. Regenerate the HTML alone via --feedback-only when
  iterating on the template. Hard-aborts on missing
  API key, failed Slidev export, slide-count mismatch, or per-slide
  click-count mismatch (script [click] count != slidev clicks for slides
  the script opts into reveals). See voice-clone-setup.md for one-time
  per-user setup.
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

## One-time per-user setup

**Before first use,** follow `voice-clone-setup.md` (in this skill
directory) to:

1. Pick an ElevenLabs tier (Pro recommended for commercial Udemy courses)
2. Record a ~2-minute voice clone sample
3. Create your Instant Voice Clone in the ElevenLabs web UI
4. Generate an API key
5. Populate `.env` in this skill directory

This is **a one-time setup per user**. The same `.env` is reused across
every Udemy course you build with this plugin. Do NOT create per-course
`.env` files.

## Environment contract

The following variables must be set in `.env` (in this skill directory):

| Variable | Required | Notes |
|---|---|---|
| `ELEVENLABS_API_KEY` | YES | ElevenLabs API key. Hard-abort if missing. |
| `ELEVENLABS_VOICE_ID` | YES | Voice ID of your cloned narration voice. |

The pronunciation dictionary ID + version are **NOT** env vars — they're
auto-managed per-course in `<course_root>/course-metadata/tts-config.json`.

Copy `.env.example` to `.env` and fill in the values. The `.env` file is
gitignored.

## Per-course pronunciation overrides

The skill ships a universal tech-term lexicon at
`pronunciation.template.pls` (acronyms spelled phonetically: "ay pee eye"
for API, "ess dee kay" for SDK, "jay-sahn" for JSON, etc.).

**Format requirements (see `playbook.md` for the full why):**

- All entries use `<alias>` rules (NOT `<phoneme>`). `eleven_multilingual_v2`
  silently ignores phoneme rules — the parser warns if you accidentally add one.
- Alias text must be **phonetic English spelling** that produces the desired
  sound when read literally. `<alias>A P I</alias>` (letter-spaced) gets
  mumbled into one word; `<alias>ay pee eye</alias>` (phonetic) reads as
  three distinct letters.

Each course MAY add its own jargon at:

```
<course_root>/course-metadata/pronunciation.pls
```

At render time, `tts_render.py`:

1. Merges the skill template with the per-course PLS (course entries win
   on grapheme conflict)
2. Computes SHA-256 of the merged content
3. Reads `<course_root>/course-metadata/tts-config.json` — if the cached
   sha256 matches, reuses the cached `pronunciation_dictionary_id` +
   `version_id`
4. Else uploads the merged PLS to ElevenLabs via
   `POST /v1/pronunciation-dictionaries/add-from-file`, captures the
   returned IDs, writes them back to `tts-config.json`

Both `pronunciation.pls` and `tts-config.json` should be **committed to
git** in the course repo. The audit trail is useful and the upload-once
contract is reproducible.

## Prerequisites

- **Python 3.9+** with packages from `requirements.txt` installed:
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
  lectures in a course.
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

### Full render (smoke test for one lecture)

```bash
python /path/to/udemy-lecture-video-renderer/render.py \
  --lecture 2.1 \
  --course-root /path/to/your-course \
  --out artifacts/lectures/lecture-2.1.mp4
```

### Partial renders

```bash
# Regenerate audio only (e.g. after tuning voice settings)
python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --audio-only

# Regenerate slides only (e.g. after updating the Slidev deck)
python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --slides-only

# Re-mux from existing assets (fastest — no API calls, no slidev export)
python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --mux-only

# Regenerate the per-lecture feedback HTML page only (no audio/video/slide re-render).
# Use this when iterating on the HTML template itself.
python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --feedback-only

# Force full re-render (ignore all cached assets)
python render.py --lecture 2.1 --course-root . --out lecture-2.1.mp4 --force
```

### Feedback workflow (after a render)

Every full render automatically writes a branded feedback HTML at
`<course_root>/feedback/lecture-X.Y/index.html` (alongside the MP4).
Open it in any browser, watch the MP4 alongside, type/paste feedback per
slide (text autosaves to localStorage; paste/drop images attach via
IndexedDB), and click **Export bundle (JSON)** when done.

**Server-side auto-save (primary path).** When the page is served by
`feedback_server.py` (see `playbook.md` → "Server-side save + unpack"),
the Export button POSTs the bundle to `/api/save-bundle`. The server
writes `<course_root>/feedback/<date>/X.Y-feedback-bundle-<ts>.json`
AND invokes `unpack_feedback.unpack()` inline to produce the round-N
markdown + extracted images — no manual `unpack_feedback.py` step needed.
A toast confirms the saved markdown path. Launch the server via the
course's `.claude/launch.json` (`feedback-preview` config) or directly:

```bash
python feedback_server.py --port 8767 --directory <course_root> \
    --lecture-output-root /Volumes/Dev_SSD/.../Course-Name/lectures
```

**`/lectures/` bridge route.** When lecture MP4s + assets dirs live on the
external SSD (the `--lecture-output-root`), the feedback HTML renders
slide thumbnails via `/lectures/section-N/.lecture-X.Y-assets/slide-NN-cM.png`.
`feedback_server.py` resolves these against the configured root with
path-traversal protection. Returns 503 if the root volume isn't mounted.

**Browser-download fallback.** If `feedback_server.py` isn't running (or
the page is opened via `file://` or against `python -m http.server`), the
Export button falls back to a browser download. Run the unpacker manually:

```bash
python /path/to/udemy-lecture-video-renderer/unpack_feedback.py \
    ~/Downloads/feedback-bundle-2.1-2026-05-24T13-19-18.json
```

That writes:
- `<course_root>/feedback/<date>/X.Y-video-generation-feedback-N.md`
- `<course_root>/feedback/<date>/X.Y-feedback-images-N/*.png` (if attachments)

`N` auto-increments based on existing files for that lecture + date. The
markdown matches the round-1-3 convention used during the lecture-2.1 polish
loop (`# Slide N (Title)` headings with bullet feedback + image references).

The entire `feedback/` directory is gitignored — feedback artifacts stay
local. The source of truth is the script + slidev edits the feedback triggers.

### Per-module CLIs (debugging)

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

## Course conventions the skill assumes

Any course consuming this skill must follow these conventions:

| Path | Purpose |
|---|---|
| `<course_root>/scripts/section-NN-<slug>/X.Y-<title>.md` | Lecture scripts with `## SLIDE N: Title` headings |
| `<course_root>/slidev/section-N.md` | One Slidev deck per section; per-lecture boundaries marked with `<!-- LECTURE X.Y — Title -->` |
| `<course_root>/course-metadata/pronunciation.pls` | OPTIONAL course-specific PLS overrides |
| `<course_root>/course-metadata/tts-config.json` | AUTO-MANAGED cache of uploaded pronunciation dictionary IDs |

## Script format contract

Lecture scripts must have `## SLIDE N: Title` headings (one per slide). The
heading line itself is not narrated. Lines starting with `**Visual**:` and
`**Camera direction**:` are stripped. Fenced code blocks are stripped (code
on screen, not read aloud). `[click]` markers split each slide's narration
into sub-chunks (one per click state) — the text BEFORE the first `[click]`
plays while the slide is in its initial state, each subsequent sub-chunk
plays after its corresponding slidev click reveals the next chunk. Inline
`**bold**` and `*italic*` markdown emphasis is stripped (text preserved);
list-bullet hyphens are stripped.

## Slide alignment + click reveals

**Slide count rule:** script SLIDE count == slidev slide count for the
lecture (using slidev's effective slide numbering, after dropping
style-only parts that slidev absorbs). Script SLIDE 1's narration plays
directly over the slidev lecture-cover slide (no synthesized cover); SLIDE
N narration plays over slidev slide N. Convention: SLIDE 1 should be
cover-flavored intro narration. See `udemy-lecture-writer/SKILL.md`. The
renderer hard-aborts if script/slidev slide counts don't match.

**Click reveals (per-click visual frames via Playwright):** each `[click]`
marker in a script SLIDE's narration splits that slide's narration into
sub-chunks. For chunked slides, the renderer drives a headless Chromium
against the running Slidev dev server (port `3020 + section_num * 10`) to
capture one PNG per click state, then `tts_render.py` emits one MP3 per
sub-chunk, and `mux.py` pairs them 1:1 — producing a video where the slide
visually unfolds in chunks as the narration explains each chunk.

The Playwright approach was added because Slidev v51's `--range` CLI flag
is broken (accepts the arg but doesn't trim the PDF). The Slidev RUNTIME
handles clicks correctly, so we drive that directly instead. See
`playbook.md` "Per-click visual capture via Playwright" for the full
write-up + the `slidev/package.json` port convention.

**Mixed-mode lectures:** slides with `script_click_count == 0` capture
only the final-revealed state (`slide-NN-c0.png`), regardless of how many
clicks slidev defines. This lets bullet/list slides "just work" without
forcing click-alignment on every slide; opt in per-slide via the script
`[click]` markers. Pure-static lectures (no `[click]` markers anywhere)
skip Playwright entirely and use the static `slidev export → pdftoppm`
path — faster, no dev-server requirement.

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

## Related skills

- `udemy-lecture-writer` — writes the lecture scripts this skill consumes.
- `udemy-slide-creator` — produces the Slidev decks this skill exports.
- `slidev-runner` — dev/build/scope-fix for Slidev decks.
- `udemy-study-guide-renderer` — sibling Python-based renderer (PDF, not MP4).
