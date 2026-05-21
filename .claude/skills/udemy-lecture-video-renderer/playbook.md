# udemy-lecture-video-renderer — Playbook

Operating reference for the four-stage render pipeline:
`parse_lecture → tts_render → slides_export → mux`.

## Click-aware output naming (read first)

All per-asset files are namespaced as `slide-NN-cM.{png,mp3,mp4}` where:
- `NN` is the slide index (1-indexed within the lecture, zero-padded)
- `cM` is the click state (0 = initial, N = final after N clicks)

A script SLIDE with `[click]` count K emits K+1 frames (`c0..cK`). A script
SLIDE with zero `[click]` markers emits exactly one frame (`c0`), and the
slidev clicks for that slide are ignored — the renderer uses the
fully-revealed final state. This per-slide opt-in lets bullet/list slides
"just work" without authoring click-aligned narration for every slide.

The mux concat order is `slide-01-c0, slide-02-c0, slide-02-c1, ...,
slide-03-c0, ...` — within each slide, all click states play in order
before advancing to the next slide.

---

## Confirmed CLI invocations

### Full smoke test (lecture 2.1)

```bash
cd /Users/jonathandyer/Documents/dev/udemy-courses/claude-architect-udemy-course
python /path/to/udemy-lecture-video-renderer/render.py \
  --lecture 2.1 \
  --course-root . \
  --out artifacts/lectures/lecture-2.1.mp4
```

Expected console output (abbreviated):
```
[parse]  lecture 2.1: 7 slides parsed (+ 1 synthesized cover = 8 total)
[tts]    slide-01.mp3  skipped (cached)   — or —  rendered 3.2s
[tts]    slide-02.mp3  rendered 11.4s
...
[slides] section-2.pdf cached (/tmp/section-2.pdf mtime ok)
[slides] lecture 2.1: slidev pages 3-10 → slide-01.png … slide-08.png
[mux]    segment-01.mp4 … segment-08.mp4
[mux]    concat → artifacts/lectures/lecture-2.1.mp4  (9m 14s, 148 MB)
DONE: artifacts/lectures/lecture-2.1.mp4
```

### Parse only (debugging script parsing)

```bash
python parse_lecture.py \
  --lecture 2.1 \
  --course-root /path/to/course | python -m json.tool
```

Expected: JSON array of 7 objects with `slide_n`, `narration_text`,
`click_count` fields. No `**Visual**:` lines. No fenced code blocks.
`[click]` converted to `<break time="0.8s" />`.

### TTS render only

```bash
python tts_render.py \
  --lecture 2.1 \
  --course-root /path/to/course \
  --out-dir /tmp/lecture-2.1-assets
```

Produces `/tmp/lecture-2.1-assets/slide-01.mp3` through `slide-08.mp3`.
Prints duration per slide (via ffprobe).

### Slides export only

```bash
python slides_export.py \
  --lecture 2.1 \
  --course-root /path/to/course \
  --out-dir /tmp/lecture-2.1-assets
```

Exports section-2 PDF to `/tmp/section-2.pdf` if not cached, then slices
pages 3-10 into `slide-01.png` … `slide-08.png`.

### Mux only

```bash
python mux.py \
  --assets-dir /tmp/lecture-2.1-assets \
  --output /tmp/lecture-2.1.mp4
```

Reads paired `slide-NN.png` + `slide-NN.mp3` files, produces segments, concats.

---

## ffmpeg flags reference

### Per-slide segment

```bash
ffmpeg -loop 1 -i slide-NN.png -i slide-NN.mp3 \
  -c:v libx264 \
  -tune stillimage \
  -pix_fmt yuv420p \
  -c:a aac \
  -b:a 192k \
  -shortest \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
  -y \
  segment-NN.mp4
```

Flag rationale:
- `-loop 1` — hold the PNG as a static input stream
- `-tune stillimage` — libx264 tuning for still images (low motion, high quality)
- `-pix_fmt yuv420p` — broadest player compatibility
- `-c:a aac -b:a 192k` — 192 kbps AAC for voice narration quality
- `-shortest` — stop when the MP3 ends (PNG stream is infinite)
- `-vf scale=1920:1080...pad...black` — letterbox / pillarbox to 1080p without distortion
- `-y` — overwrite output if it exists

### Final concat

```bash
ffmpeg -f concat -safe 0 -i concat-list.txt -c copy -y lecture-X.Y.mp4
```

`concat-list.txt` format:
```
file 'segment-01.mp4'
file 'segment-02.mp4'
...
```

`-c copy` — stream copy; no re-encoding. The concat is fast (seconds, not minutes).

---

## Slidev export + page slicing

### Export command

```bash
cd <course_root>/slidev
npx slidev export section-N.md --output /tmp/section-N.pdf
```

Timeout: 300s. If it hangs past that, kill and retry once. If it fails twice,
check Node.js version (`node --version` >= 18) and that Playwright deps are
installed (`npx playwright install chromium`).

### pdftoppm invocation

```bash
pdftoppm -png -r 150 /tmp/section-N.pdf /tmp/section-N-page
```

Produces `/tmp/section-N-page-001.png`, `-002.png`, etc. The `-r 150`
resolution gives 150 DPI → adequate quality for 1920x1080 scaling.

### Page-range logic for a lecture

1. Parse `section-N.md`; find `<!-- LECTURE X.Y -->` boundary.
2. Count `^---$` slide separators after the LECTURE comment up to the next
   `<!-- LECTURE -->` marker or EOF.
3. Add 2 to account for the Slidev frontmatter slide (page 1) plus the
   section-level separator between lectures.
4. Pages are 1-indexed; rename to `slide-01.png` … `slide-NN.png`.

Log to stderr:
```
Lecture 2.1: slidev pages 3-10 → slide-01.png to slide-08.png
```

---

## ElevenLabs API reference

### TTS endpoint (Python SDK)

```python
from elevenlabs import ElevenLabs, VoiceSettings
from elevenlabs.types import PronunciationDictionaryVersionLocator

client = ElevenLabs(api_key=api_key)
audio_stream = client.text_to_speech.convert(
    voice_id=voice_id,
    text=narration_text,        # may contain <break time="0.8s" /> SSML
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
    voice_settings=VoiceSettings(
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=True,
    ),
    pronunciation_dictionary_locators=[
        PronunciationDictionaryVersionLocator(
            pronunciation_dictionary_id=dict_id,
            version_id=dict_version,
        )
    ],  # omit entirely if dict_id not set
)
with open("slide-NN.mp3", "wb") as f:
    for chunk in audio_stream:
        f.write(chunk)
```

### Duration check via ffprobe

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 slide-NN.mp3
```

Returns a float (seconds). Log as `slide-NN.mp3: 11.4s`.

### Pronunciation dictionary — auto-managed per course

**No manual upload required.** `tts_render.py` handles the entire flow:

1. Loads the skill template `pronunciation.template.pls` (universal tech terms)
2. Loads `<course_root>/course-metadata/pronunciation.pls` if it exists
   (course-specific overrides; entries override the template on grapheme conflict)
3. Merges the two into a deterministic, sorted PLS string and computes its SHA-256
4. Reads `<course_root>/course-metadata/tts-config.json` cache
5. If the cached `pls_sha256` matches the new hash → reuse cached
   `id` + `version_id`. No upload.
6. Otherwise → `POST /v1/pronunciation-dictionaries/add-from-file` with the
   merged PLS, capture the returned `id` and `version_id`, and write back to
   `tts-config.json`

Equivalent manual curl (if you want to inspect the upload yourself):

```bash
curl -X POST https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -F "file=@merged.pls;type=application/pls+xml" \
  -F "name=<course-slug> — auto-merged"
```

The skill names the dictionary `"<course_dir_name> — auto-merged"` so you
can identify it later in the ElevenLabs dashboard.

**To force a re-upload** (e.g. after editing the PLS): delete the
`pronunciation_dict` block from `tts-config.json` (or the whole file), or
just modify any character in either PLS file — the SHA-256 will change and
the next render auto-uploads.

---

## Idempotency rules

| Asset | Skip condition |
|---|---|
| `slide-NN.mp3` | File exists, size > 0, mtime > source script mtime, `--force` not set |
| `/tmp/section-N.pdf` | File exists, mtime > `section-N.md` mtime, `--force` not set |
| `slide-NN.png` | File exists, size > 0, mtime > `/tmp/section-N.pdf` mtime, `--force` not set |
| `segment-NN.mp4` | File exists, size > 0, mtime > both `slide-NN.png` and `slide-NN.mp3` mtime, `--force` not set |

Re-running `render.py` with all assets present and up-to-date completes in
< 5 seconds (full cache hit).

---

## Troubleshooting matrix

### TTS errors

| Symptom | Cause | Fix |
|---|---|---|
| `AuthenticationError` / 401 | `ELEVENLABS_API_KEY` missing or expired | Check `.env`; generate new key at elevenlabs.io → Profile → API |
| `ValidationError` on `voice_id` | Voice not in your account | Check `ELEVENLABS_VOICE_ID`; list voices via `GET /v1/voices` |
| `quota_exceeded` / 402 | Credit limit hit | Upgrade plan or wait for credit reset |
| `PronunciationDictionaryVersionLocator` import error | SDK < 1.0 | `pip install --upgrade elevenlabs` |
| SSML `<break>` not honored | `eleven_turbo_v2` ignores SSML | Switch to `eleven_multilingual_v2` (already locked) |
| Audio sounds wrong voice | `ELEVENLABS_VOICE_ID` points to wrong clone | Verify via ElevenLabs dashboard → My Voices |
| Empty `.mp3` written | Stream returned zero bytes | Check text was non-empty after stripping; re-run `--force` |

### Slidev export failures

| Symptom | Cause | Fix |
|---|---|---|
| `npx: command not found` | Node.js not installed | `brew install node` |
| Export hangs > 300s | Playwright not installed | `cd slidev && npx playwright install chromium` |
| `Cannot find module './section-N.md'` | Wrong working directory | Ensure CWD is `<course_root>/slidev/` before running npx |
| PDF page count differs from expected | Wrong lecture boundary in section .md | Inspect `<!-- LECTURE X.Y -->` markers in the deck |
| No PDF output but no error | Playwright headless crash | Run `PWDEBUG=1 npx slidev export ...` to see browser errors |

### ffmpeg encoding errors

| Symptom | Cause | Fix |
|---|---|---|
| `libx264 not found` | ffmpeg installed without libx264 | `brew reinstall ffmpeg` or `brew install ffmpeg --with-libx264` |
| `Invalid data found when processing input` on PNG | Corrupted PNG from pdftoppm | Re-run `slides_export.py --force` to regenerate PNGs |
| `Moov atom not found` on MP3 | Truncated MP3 from TTS | Delete the offending `.mp3` and re-run `tts_render.py --force` |
| Concat output has no audio | Segment MP4s have mismatched stream indices | Re-mux each segment; avoid mixing aac-only and video-only streams |
| Output MP4 plays in black (no video) | PNG dimensions not divisible by 2 after scale | The `pad` filter handles this; ensure `scale=1920:1080` is present |
| `concat-list.txt: No such file` | `mux.py` ran before segments were written | Run full `render.py` first; don't call `mux.py` standalone until segments exist |

### Slide-count mismatch

| Symptom | Cause | Fix |
|---|---|---|
| `AssertionError: expected 8 slides, got 9` | Slidev deck has an extra separator `---` in the lecture range | Inspect section .md around the LECTURE boundary; remove stray `---` |
| `AssertionError: expected 8 slides, got 7` | Script has one more SLIDE heading than Slidev pages | Check if the last SLIDE heading was accidentally left without a corresponding `---` in the deck |
| Cover narration auto-generated but sounds wrong | `<!-- LECTURE X.Y — Title -->` marker text differs from expected | Edit the LECTURE comment in the deck to match the script title |

---

## System dependencies checklist

Run before first use:

```bash
# All four required binaries
which ffmpeg && ffmpeg -version | head -1
which ffprobe && ffprobe -version | head -1
which pdftoppm && pdftoppm -v 2>&1 | head -1
node --version
npx --version

# Python packages
pip show elevenlabs python-dotenv

# Verify .env is populated
python -c "
import os; from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('$(pwd)/.env'))
for k in ['ELEVENLABS_API_KEY','ELEVENLABS_VOICE_ID']:
    v = os.getenv(k,'')
    print(k, 'SET' if v else 'MISSING')
"
```
