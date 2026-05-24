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
# audio_dur = ffprobe -show_entries format=duration  (probed per MP3)
ffmpeg -loop 1 -i slide-NN.png -i slide-NN.mp3 \
  -c:v libx264 \
  -tune stillimage \
  -pix_fmt yuv420p \
  -r 25 \
  -g 25 \
  -c:a aac \
  -b:a 192k \
  -t <audio_dur> \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
  -y \
  segment-NN.mp4
```

Flag rationale:
- `-loop 1` — hold the PNG as a static input stream
- `-tune stillimage` — libx264 tuning for still images (low motion, high quality)
- `-pix_fmt yuv420p` — broadest player compatibility
- `-r 25 -g 25` — 25 fps + keyframe every 25 frames (1s). Clean keyframe boundaries help the concat demuxer stitch segments without artifacts at segment seams.
- `-c:a aac -b:a 192k` — 192 kbps AAC for voice narration quality
- `-t <audio_dur>` — **CRITICAL**: explicit output duration probed from the MP3. See "Per-segment silent-tail bug" below for the full diagnosis. Replaces `-shortest`, which is unreliable with `-loop 1` and leaves 1-3s of silent video tail on segments >8s.
- `-vf scale=1920:1080...pad...black` — letterbox / pillarbox to 1080p without distortion
- `-y` — overwrite output if it exists

### Per-segment silent-tail bug (fixed via `-t <audio_dur>`)

**Symptom:** A perceptible "hiccup" or dead-air gap at click reveals and
slide transitions in the concat'd final MP4. Most noticeable mid-slide at
click boundaries (e.g. SLIDE 3 click 0 → click 1 in lecture 2.1 demo —
hit at ~1:27 on a 5:37 video) because the viewer's brain expects the next
reveal to fire as soon as narration ends; instead the slide sits silent
for 2-3 seconds before the click happens.

**Root cause:** `-shortest` is unreliable in combination with `-loop 1`
input. For segments longer than ~8 seconds of audio, the encoder
overshoots the audio end by 1-3 seconds (likely encoder lookahead or PTS
rebasing interactions — the exact mechanism is murky). Short bullet-slide
segments happen to escape it. Adding `-r 25 -g 25` (1-second keyframe
spacing) partially helps — reduces the gap from ~2.3s to ~1.6s — but does
not fully eliminate it. The bulletproof fix is to skip `-shortest`
entirely and pass `-t` with the exact audio duration probed beforehand.

**Diagnostic:**
```bash
# Compare audio vs video stream durations on each segment
for f in segment-*.mp4; do
  v=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$f")
  a=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$f")
  gap=$(awk -v v="$v" -v a="$a" 'BEGIN{printf "%.2f", v-a}')
  echo "$f  video=$v  audio=$a  gap=${gap}s"
done
```

Healthy segments show `gap` ≈ 0s (within ±0.02s). Buggy segments show
1.6-3s gap. The bug is sporadic across slides — it depends on audio
duration; clips under ~8s often escape it, longer clips reliably hit it.

**Fix:** in `mux.py`, probe the audio duration via `_probe_duration()`
and pass `-t {audio_dur:.3f}` to the segment encoder INSTEAD of
`-shortest`. After the fix, all segments verify ±0.02s.

### Final concat

```bash
ffmpeg -f concat -safe 0 -i concat-list.txt \
  -c:v libx264 \
  -tune stillimage \
  -preset veryfast \
  -crf 20 \
  -pix_fmt yuv420p \
  -r 25 \
  -g 25 \
  -bf 0 \
  -c:a aac \
  -b:a 192k \
  -movflags +faststart \
  -y \
  lecture-X.Y.mp4
```

`concat-list.txt` format:
```
file 'segment-01.mp4'
file 'segment-02.mp4'
...
```

Flag rationale:
- `-c:v libx264 -tune stillimage -preset veryfast -crf 20` — full re-encode (not `-c copy`). See "Concat re-encode rationale" below.
- `-bf 0` — disable b-frames in the concat output. B-frames in stream-copy concat is what caused QuickTime to render black frames (see rationale).
- `-r 25 -g 25` — 25 fps + 1s keyframe interval, consistent across the whole file (matches the per-segment encode).
- `-movflags +faststart` — moves the moov atom to the front of the file so the MP4 is seekable/streamable without downloading the tail first. Required for Udemy's player + most browser players.

### Concat re-encode rationale (instead of `-c copy`)

**What changed:** the original mux used `-c copy` to stream-copy each
segment's packets into the final MP4 unchanged. Concat-by-copy is fast
(~2s for a 5-min lecture vs ~20s for a re-encode) but fragile.

**Symptom of the fragility:** the concat'd MP4 plays fine in ffmpeg /
VLC / Chrome, but QuickTime renders a **black frame with no audio** for
the entire duration. The file is technically valid — `ffprobe` reads it,
`ffmpeg` decodes individual frames from it — but QuickTime's stricter
decoder rejects it silently.

**Diagnostic signatures of a broken concat-by-copy MP4:**
- `start_pts=294, start_time=0.022969` (small but nonzero offset at the start)
- `avg_frame_rate=32614400/1305169` ≈ 24.987 fps while `r_frame_rate=25/1` (rate mismatch)
- `has_b_frames=2` (b-frames present, which interact badly with the per-segment PTS rebasing during concat)

**Compare to a clean re-encoded concat:**
- `start_pts=0, start_time=0.000000`
- `r_frame_rate == avg_frame_rate == 25/1`
- `has_b_frames=0`

**Why this matters at scale:** uploading a black-frame MP4 to Udemy
would silently break the lecture without any error from Udemy's
ingest pipeline. The 18-second cost per lecture for a clean re-encode
(~30 min total for 94 lectures) is dramatically cheaper than discovering
this in production.

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

### Per-click visual capture via Playwright (replaces broken `slidev export --range`)

**Architecture:** `slides_export.py` now delegates to `playwright_capture.py` whenever the lecture's script declares any `[click]` markers (`script_click_counts` has any value > 0). This drives a headless Chromium against the running Slidev dev server and captures one PNG per click state — bypassing the broken `slidev export --range --with-clicks` CLI path entirely.

**Why this design:**

- Slidev's RUNTIME handles clicks correctly — that's why the live HTML preview at `:3040` (and the corresponding preview pane in Claude Desktop via the `slidev-section-N` launch.json entry) shows progressive reveals working.
- Only the CLI exporter is broken (see "slidev `--range` bug" notes below).
- Playwright lets us programmatically navigate to `/<slidev_page>?clicks=<M>` for each click state, wait for the runtime to render, and snapshot.

**Prerequisites:**

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

Plus: the Slidev dev server for the target section must be running. Port convention follows `slidev/package.json`: `dev:N` → port `3020 + N*10` (so section 2 = 3040, section 3 = 3050, etc.). If not running, the script aborts with a clear error pointing at the `npm run dev:N` command (or the Claude Preview MCP launch entry).

**Output naming (mux.py consumes these 1:1):**

```
slide-NN-c0.png   ← initial visible state
slide-NN-c1.png   ← after click 1 reveals chunk 1
slide-NN-cM.png   ← after click M (M = N_clicks for the slide)
```

Each PNG pairs with `slide-NN-cM.mp3` from `tts_render.py` (per sub-chunk). `mux.py` sorts by (slide_idx, click_idx) and concatenates in order. The user sees progressive reveals timed to narration sub-chunks.

**Mixed-mode lectures:** for slides where `script_click_counts[K] == 0` (no `[click]` markers in the script for that SLIDE), Playwright captures ONLY the final-state PNG (`slide-NN-c0.png`) regardless of how many clicks slidev defines. This lets bullet slides "just work" without forcing click-alignment on every slide; opt in per-slide via script `[click]` markers.

**Pure-static lectures** (no `[click]` markers anywhere → `script_click_counts` is all zeros) skip Playwright entirely and fall back to the static `slidev export → pdftoppm` path. Faster and no dev-server requirement when click alignment is unused.

**Click-count validation:** for each slide where `script_clicks > 0`, Playwright reads `window.__slidev__.nav.clicksTotal` to verify it matches the script's declared count. Mismatch → hard abort with the offending slide's expected vs actual.

**Verification command** (no full render needed):

```bash
# With slidev dev server running on the expected port:
python3 playwright_capture.py --lecture 2.1 \
  --course-root /path/to/course \
  --out-dir /tmp/quick-capture
ls /tmp/quick-capture  # expect slide-NN-cM.png files in (slide, click) order
```

---

### ⚠️ ElevenLabs pronunciation rule types — alias vs phoneme model support

**This skill MUST use `<alias>` rules, not `<phoneme>` rules.** Discovered the hard way 2026-05-22 after a wasted render iteration where `API` came out as one mumbled word.

Per the [ElevenLabs pronunciation-dictionaries cookbook](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/pronunciation-dictionaries) and [model support docs](https://elevenlabs.io/docs/eleven-agents/customization/voice/pronunciation-dictionary):

> "Phoneme tags only work with `eleven_flash_v2` & `eleven_monolingual_v1` models. … For other languages, use alias tags instead to substitute spellings or phrases that produce the pronunciation you need. Alias tags are supported by all models."

This skill uses `eleven_multilingual_v2` (locked in `tts_render.py` for narration quality), which means:

- ✅ `<alias>` rules apply (literal text substitution at TTS preprocessing time)
- ❌ `<phoneme>` rules are **silently ignored** — the dict uploads cleanly and the rule appears via `GET /v1/pronunciation-dictionaries/{id}`, but the model just doesn't apply them

`_parse_pls_lexemes()` enforces this — phoneme-only entries trigger a `WARN: contains N phoneme-only entries — these are SILENTLY IGNORED` stderr message so anyone editing a PLS file gets immediate feedback if they regress.

**Alias text format — phonetic English, not letter-spacing**. The alias text is read literally by the model. So:

| Wrong | Right | What the model says |
|---|---|---|
| `<alias>A P I</alias>` | `<alias>ay pee eye</alias>` | "ay pee eye" (3 distinct letters) |
| `<alias>S D K</alias>` | `<alias>ess dee kay</alias>` | "ess dee kay" |
| `<alias>Anthropic</alias>` | `<alias>an-THROP-ick</alias>` | "an-THROP-ick" |
| `<alias>JSON</alias>` | `<alias>jay-sahn</alias>` | "jay-sahn" |

Letter-spaced aliases (`"A P I"`) get chunked into one mumbled word by `eleven_multilingual_v2`. Phonetic English spellings ALWAYS work because the model is doing what TTS does best: reading written English aloud.

**Both PLS files in this codebase already follow this convention** — `pronunciation.template.pls` (skill) and `<course>/course-metadata/pronunciation.pls` (per-course override). If you add a new entry, use phonetic English spelling.

**Verifying a dict is actually being applied at TTS time**:

```bash
# Print the rules ElevenLabs has stored for your cached dict
DICT_ID=$(python3 -c "import json; print(json.load(open('<course>/course-metadata/tts-config.json'))['pronunciation_dict']['id'])")
source <skill>/.env
curl -sS "https://api.elevenlabs.io/v1/pronunciation-dictionaries/$DICT_ID" -H "xi-api-key: $ELEVENLABS_API_KEY" | python3 -m json.tool
# Every rule should have "type": "alias". If you see "type": "phoneme", the rule is being silently ignored.
```

---

### Pronunciation gotchas (observed during lecture 2.1 render iterations)

These traps were observed during lecture 2.1's first render and the fix-and-re-render cycles that followed. When adding new identifiers to a lecture script, scan the narration text for any of the patterns below and apply the appropriate fix BEFORE rendering.

| Trap | Symptom | Fix |
|---|---|---|
| Underscores in identifiers (e.g. `stop_reason`, `stop_sequence`, `max_tokens`, `tool_use`) | Reads as "Stop-R-reason" / "stop harsh sequence" / non-deterministic mix across slides | Add to course `pronunciation.pls` as `<lexeme><grapheme>stop_reason</grapheme><alias>stop reason</alias></lexeme>` (alias = grapheme with underscores → spaces). **`parse_lecture.py` auto-warns on every render if an underscored identifier in the narration is missing from the merged PLS** — see `_audit_pronunciation` (round-3 addition). Fix the warning before re-render. |
| Bare array indices (`[0]`, `[1]`) | Trips the TTS rhythm — sounds like "zo" or gets skipped entirely | Spell out in narration: *"the first item"*, *"the second item"*, or *"index zero"*. Authoring convention; see `udemy-lecture-writer/SKILL.md` Rule 3. |
| Bare dot notation (e.g. `.text` standalone) | Sounds clipped, runs into surrounding words | Surround with comma pause in the narration: *", dot text"*. Or rephrase to avoid the bare attribute. |
| Mixed-case identifiers (e.g. `maxTokens`, `topK`) | TTS may read as separate words OR as one slurred word, inconsistent across slides | Add to PLS as `<alias>max tokens</alias>` if used repeatedly; otherwise spell out in narration. |
| Backtick-wrapped identifiers in markdown | Backticks pass through to TTS in some parser modes (legacy issue, mostly fixed) | `parse_lecture.py` strips inline backticks correctly. If pronunciation is still off, the identifier itself needs a PLS entry — not a backtick issue. |
| Letter-acronym aliasing (e.g. API) | Round-1 `<alias>ay pee eye</alias>` → "eye-pee-eye" (homophone). Round-3 `<alias>A. P. I.</alias>` → "A dot P dot I dot" (literal period-pauses). Round-4 no alias → "A pie" (slurred). | **Round-5 third attempt: `<alias>A, P, I</alias>` (commas).** Commas create micro-pauses (~50ms) without the full-stop pauses periods cause, AND the letters stay distinct so the TTS can't slur them into a word. If a future render reveals another regression, escalate to verbose `<alias>letter A, letter P, letter I</alias>`. Pattern applies to other letter-acronyms (SDK, CLI, MCP, HTTP, URL, UUID) — try the comma form first if a homophone surfaces. |
| 2-letter common-word identifiers (e.g. `id`, `ip`, `ui`, `os`) | TTS reads as homophone English word: `id` → "eyed", `os` → "oss" / "Oz" / mumbled | Same period-separated-capitals pattern as the acronym aliases: `<lexeme><grapheme>id</grapheme><alias>I. D.</alias></lexeme>`. Not auto-detected by parse_lecture (too many false positives — see lecture-writer SKILL.md Rule 3 for the manual grep recipe). |
| Ellipsis (`...` or `…`) in narration | TTS inserts a long pause (1-2s) where the dots appear — sounds like a dead air gap mid-sentence | `parse_lecture.py` auto-strips ellipses in narration cleanup (round-4 add — `_ELLIPSIS_RE` in `clean_whitespace`). No author action required. The visual on the slide is unaffected (the dots still show in the rendered code/text). For a deliberate spoken pause, use SSML `<break time="0.8s"/>` instead. |
| Aliases with ALL CAPS or hyphens (e.g. `<alias>SON-it</alias>` for Sonnet) | Hyphen creates emphasis on the second syllable, making "Sonnet" sound like "son-NAY" | Use plain lowercase with space if needed: `<alias>sahn it</alias>`. Or remove the alias entirely if the TTS reads the base term correctly — sometimes no alias is the right answer. |

**Decision rule for PLS vs script rewrite:**
- **PLS entry** — for identifiers reused across 3+ slides or multiple lectures. One entry, deterministic pronunciation everywhere.
- **Script rewrite (phonetic spelling)** — for one-off code references where the phonetic version reads more naturally than the symbolic form.

---

### ⚠️ ElevenLabs PLS upload — two undocumented format quirks (discovered 2026-05-21)

ElevenLabs's PLS validator rejects payloads that other tools (curl with default headers, W3C XML validators, Python's `xml.etree`) accept. Both quirks bit a real render iteration before we figured them out. **The renderer's `_build_merged_pls()` and `_resolve_pronunciation_dict()` already handle both — do not regress on these without an end-to-end PLS upload test against `https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file`.**

**Quirk 1 — `<lexicon>` opening tag must be on a single line.** Multi-line attribute declarations like:

```xml
<lexicon version="1.0"
         xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
         alphabet="ipa"
         xml:lang="en-US">
```

trigger `400 {"detail":{"message":"Unable to parse the lexicon file: Lexicon file formatted incorrectly"}}` even though this is valid XML. Collapse to a single line:

```xml
<lexicon version="1.0" xmlns="http://www.w3.org/2005/01/pronunciation-lexicon" alphabet="ipa" xml:lang="en-US">
```

**Quirk 2 — content-type must NOT be `application/pls+xml`.** The W3C-correct MIME type for PLS files is `application/pls+xml`, but ElevenLabs's validator rejects uploads with that explicit content-type. **Use `text/xml` or omit the content-type entirely** — both work. `tts_render.py` sends `text/xml`.

**Quick verification command** if you're debugging a PLS upload:

```bash
source <skill>/.env
curl -sS -X POST "https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -F "name=quick-test" \
  -F "file=@your-test.pls;type=text/xml"
# Success: returns {"id":"...","name":"quick-test","version_id":"..."}
# Failure: returns {"detail":{"message":"Unable to parse the lexicon file..."}}
```

Both fixes are in `tts_render.py` with inline comments referencing this playbook section. If a future ElevenLabs update relaxes the validator, both restrictions can be lifted (re-test with the curl above first).

---

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

### Orphan-asset auto-prune (Stage 1b)

After Stage 1 parse but BEFORE any TTS / slide-export / mux work, render.py
runs `_prune_orphan_assets()` which deletes per-click asset files whose
chunk index exceeds the current script's `click_count` for that slide.

The bug this fixes: if a slide previously had 5 chunks (script declared 4
`[click]` markers) and the script is later edited to have 3 chunks (2
`[click]` markers), the old `slide-NN-c3.*` and `slide-NN-c4.*` files
persist on disk. `mux.py`'s `slide-NN-c*.*` glob picks them up and pairs
them into the segment list — producing a broken MP4 (extra trailing
segments on that slide, with stale audio over stale visuals).

The prune is conservative:
- Files matching the current `click_count` are LEFT INTACT — composes
  cleanly with the per-asset mtime cache
- Slides removed from the script entirely also have ALL their per-click
  files pruned (the whole slide is an orphan)
- Pure-static slides (script `click_count == 0`) keep only `c0` — any
  `cN` where N > 0 is an orphan from a prior chunked-render pass

If you see `[render] pruned N orphan per-click asset(s)` in the log, that
means the script's chunking shrank since the last render. The prune is
silent when there's nothing to remove.

This obviates the historical workaround of `rm -rf .lecture-X.Y-assets/`
before each render. `batch_render.py` no longer wipes by default; pass
`--wipe-assets` only for the nuclear option (re-render every asset, slow,
full TTS + Playwright cost).

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
| Output MP4 plays in black in **QuickTime** but works in VLC / Chrome / ffmpeg | b-frames + stream-copy concat produce PTS QuickTime rejects | Re-encode the concat instead of `-c copy`. See "Concat re-encode rationale" — already locked in `mux.py`. Diagnostic: `ffprobe ...` shows `has_b_frames=2` and `avg_frame_rate` ≠ `r_frame_rate`. |
| `concat-list.txt: No such file` | `mux.py` ran before segments were written | Run full `render.py` first; don't call `mux.py` standalone until segments exist |
| Click/slide boundary "hiccup" — 1-3s silent pause where the next click should fire | `-shortest` overshoots audio end on segments >8s | Already fixed via `-t {audio_dur:.3f}` in `mux.py`. See "Per-segment silent-tail bug". Diagnostic: `ffprobe` per-stream `duration` shows `video - audio > 0.5s`. |

### Slide-count mismatch

| Symptom | Cause | Fix |
|---|---|---|
| `AssertionError: expected 8 slides, got 9` | Slidev deck has an extra separator `---` in the lecture range | Inspect section .md around the LECTURE boundary; remove stray `---` |
| `AssertionError: expected 8 slides, got 7` | Script has one more SLIDE heading than Slidev pages | Check if the last SLIDE heading was accidentally left without a corresponding `---` in the deck |
| Script has 10 SLIDE headings but `parse_lecture` reports 9 | A fenced code block contains a literal triple-backtick sequence in its content (e.g. ` "content": "```python\n" ` inside a JSON example) — the non-greedy code-fence regex matched the inner backticks as the closing fence and swallowed everything up to the NEXT real fence, including a downstream `## SLIDE N:` heading | Fixed in `_CODE_FENCE_RE` (anchored to line starts per CommonMark §4.5). If you see this again, run `python -c "import re; rx=re.compile(r'\`\`\`.*?\`\`\`',re.DOTALL); print([m.group(0)[:60] for m in rx.finditer(open('script.md').read())])"` to find the offending block, then verify both fences sit on their own line. |
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

---

## Per-lecture feedback HTML (branded review tool)

Every successful render writes a self-contained, Dyer-Innovation-branded
HTML page at `<course_root>/feedback/lecture-X.Y/index.html`. Open in any
browser — it's pure HTML + CSS + vanilla JS, no server needed.

### What's on the page

- Sticky header: logo, lecture title, slide-count meta, "Export bundle"
  button
- One card per `## SLIDE N:` heading from the script, in order. Each card has:
  - Slide number + title (extracted from the script's `## SLIDE N: Title`)
  - Thumbnail strip of all `slide-NN-cM.png` files for that slide (click to zoom)
  - Free-text feedback textarea (autosaves to `localStorage`)
  - Paste/drag-drop image zone (binary stored in `IndexedDB`)
  - Attached-images list with per-image delete buttons
- Footer: "with feedback" counter + Clear-all button

### Generation contract

`generate_feedback_html.py` is auto-invoked by `render.py` at the end of a
full render (after mux) and the end of `--slides-only`. It reads the script
for slide titles + the assets dir for PNG enumeration, embeds the logo as a
base64 data URI, and uses relative paths back into the assets dir for
thumbnail `<img src>` resolution. No internet required after generation
(Google Fonts is loaded over the network for typography — the rest is local).

For regeneration without a full re-render:

```bash
python render.py --lecture 2.1 --course-root . \
    --out artifacts/lectures/lecture-2.1.mp4 --feedback-only
```

This is the right command after editing `feedback_template.html` itself.

### Export → markdown round-trip

The "Export bundle (JSON)" button serializes localStorage feedback + IndexedDB
image blobs (base64-encoded) into a single
`feedback-bundle-X.Y-<timestamp>.json` file the browser downloads.

`unpack_feedback.py` turns that bundle into the round-N markdown format
used during the lecture-2.1 polish loop:

```bash
python unpack_feedback.py ~/Downloads/feedback-bundle-2.1-*.json
```

Writes:
- `<course_root>/feedback/<date>/X.Y-video-generation-feedback-N.md`
- `<course_root>/feedback/<date>/X.Y-feedback-images-N/*.png`

The N suffix auto-increments based on existing files in the date directory,
matching how the lecture-2.1 polish rounds (-1 through -3) were captured.

### Markdown format (matches rounds 1-3)

```markdown
# Lecture 2.1 feedback — round 1
_The Messages API: Anatomy of a Request and Response_

Exported: 2026-05-24T13:19:18.013Z

# Slide 5 (A Complete Request, Annotated)
- API mentioned at ~0:35.
- Second paragraph here.
- ![Slide 5 screenshot](2.1-feedback-images-1/test-screenshot.png)

# Slide 7 (The Four Values of stop_reason)
- bullet one
- bullet two should be split
```

Text-area handling:
- Blank lines in the textarea → separate bullets
- Lines starting with `- ` or `* ` → one bullet per line
- Single-paragraph multi-line text → one bullet (lines joined with spaces)

### Why per-lecture HTML (not a single dashboard)

Choice from the scale-up plan: one HTML per lecture keeps refresh-on-build
clean (each render touches only its own HTML), feedback for completed
lectures stays accessible after rendering the next batch, and the iteration
loop classifies bundles by lecture ID at unpack time.

### Why JSON bundle (not direct file write)

The HTML runs in a sandboxed browser without filesystem write access (and we
deliberately don't use the Chrome-only File System Access API for portability).
JSON download + Python unpacker works in every modern browser and gives the
unpacker free reign to organize files server-side (date dirs, image folders,
revision numbering).

### Storage isolation

- localStorage key: `feedback-X.Y` (one key per lecture, JSON object keyed by slide number)
- IndexedDB database: `lecture-feedback-images` (one shared DB across lectures, store `blobs`, keys prefixed `img:X.Y:<slide_n>:<timestamp>`)

Per-lecture pages don't see other lectures' state (different localStorage
key + IndexedDB key prefix).

### When to regenerate the HTML

- After ANY render — automatic
- After editing slide titles in the script — re-run `--feedback-only`
- After editing the HTML template — re-run `--feedback-only`
- NOT needed when only narration text changed (titles drive the HTML, not narration)

---

## Server-side save + unpack (`feedback_server.py`)

The default `python -m http.server` is fine for static preview but can't
help the Export button write the bundle to disk (browser sandbox blocks
direct file I/O). `feedback_server.py` is a stdlib-only drop-in that adds
two endpoints on top of plain static serving.

### Endpoints

| Method + path | Behavior |
|---|---|
| `POST /api/save-bundle` | Accepts the export-button JSON, writes `<course_root>/feedback/<date>/X.Y-feedback-bundle-<ts>.json`, then invokes `unpack_feedback.unpack()` in-process. Returns 200 `{ok, bundle_path, markdown_path, markdown_relative, image_count}`. 400 on bad JSON / missing `lecture` / missing `slides`. CORS-permissive; `OPTIONS` preflight returns 204. |
| `GET /lectures/<rest>` | Serves files from `--lecture-output-root` (default: external SSD). 404 if the file doesn't exist under the root. 503 if the configured root doesn't exist (e.g. SSD unmounted). 400 if a request tries to escape the root via `..` — see "Path traversal guard" below. |
| `GET /api/health` | JSON status: `{ok, course_root, lecture_output_root, lecture_output_root_mounted}`. Useful for `curl` verification + the launch.json health-check pattern. |
| anything else | Falls through to `SimpleHTTPRequestHandler` serving from `--directory`. URLs like `/feedback/lecture-2.2/index.html` and `/artifacts/lectures/.lecture-2.1-assets/slide-01-c0.png` still work for backwards compatibility. |

### CLI

```bash
python feedback_server.py \
  --port 8767 \
  --directory /Users/jonathandyer/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --lecture-output-root /Volumes/Dev_SSD/Dyer_Innovation_Lecture_Videos/Udemy/Claude-Architect-Course/lectures
```

Defaults:
- `--port 8767`
- `--directory .`
- `--lecture-output-root /Volumes/Dev_SSD/Dyer_Innovation_Lecture_Videos/Udemy/Claude-Architect-Course/lectures`
- `--bind 127.0.0.1` (loopback only — change to `0.0.0.0` only if you really want LAN exposure)

On startup the server prints a banner with the resolved config + a copy-pasteable curl example.

### Path traversal guard

`/lectures/<rest>` resolves `<rest>` against the configured root using
`Path.resolve()` and then verifies the resolved target is the root itself
OR has the root as one of its parents. Any request whose resolved path
escapes the root tree (`/lectures/../etc/passwd` sent verbatim via
`curl --path-as-is`) returns 400 `{"ok": false, "error": "invalid path
(traversal blocked)"}`. Browsers and well-behaved HTTP clients normalize
`..` segments client-side before sending, so the guard mostly catches
hand-crafted requests.

### Why stdlib

The skill stays portable across whichever Python the user points at it
(course conventions lock that to `/usr/bin/python3`). No flask /
aiohttp / werkzeug install required. The threading TCP server
(`socketserver.ThreadingTCPServer` with `allow_reuse_address = True`) is
enough for one-at-a-time interactive feedback work.

### Replacing `python -m http.server` in launch.json

Update the `feedback-preview` config in `<course_root>/.claude/launch.json`:

```jsonc
{
  "name": "feedback-preview",
  "runtimeExecutable": "/usr/bin/python3",
  "runtimeArgs": [
    "/Users/jonathandyer/Documents/dev/udemy-courses/udemy-course-builder/.claude/skills/udemy-lecture-video-renderer/feedback_server.py",
    "--port", "8767",
    "--directory", ".",
    "--lecture-output-root", "/Volumes/Dev_SSD/.../Course-Name/lectures"
  ],
  "port": 8767
}
```

The `feedback_template.html` Export button POSTs to `/api/save-bundle`
first; on any failure (network error, non-2xx, missing server) it falls
back to the original browser-download path — so the HTML stays usable
against `python -m http.server` or `file://` for users who haven't
migrated their launch.json.
