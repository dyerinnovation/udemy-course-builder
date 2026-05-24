---
name: udemy-video-uploader
description: >
  Upload rendered lecture .mp4 files into Udemy course lectures via Chrome
  MCP / Playwright browser automation. Reads MP4s produced by
  `udemy-lecture-video-renderer` (default path
  `<course_root>/artifacts/lectures/lecture-X.Y.mp4`) and walks the
  `[data-purpose="lecture-add-content-btn"]` → "Video" picker → file-upload
  → wait-for-transcode → save flow per lecture. Sibling of
  `udemy-resource-uploader` (same dashboard, same `data-purpose` selector
  strategy, same auth backends, same idempotency + safety rules) but targets
  the lecture's PRIMARY content type (Video) rather than the additive
  Resources sub-panel. Idempotent (skips lectures that already have a Video
  attached unless `--force-replace`), supports `--dry-run` / `--preview`
  preview mode, and pauses for explicit user confirmation before any
  destructive replace. Never publishes; never deletes anything other than an
  existing video when `--force-replace` is explicitly requested. Use AFTER
  `udemy-curriculum-populator` has created the lecture stubs and AFTER
  `udemy-lecture-video-renderer` has produced the MP4s; this skill closes the
  final-mile gap between rendered video on disk and live lecture in the
  instructor dashboard. Supports single-lecture, multi-lecture, and
  whole-section runs via `--lectures 2.1,2.2,2.3` or `--section 2` flags.
  STUB-LEVEL v0 — selector confirmations and the actual Chrome MCP /
  Playwright invocations are TODO and will be filled in on first real
  `--apply` run, mirroring how `udemy-resource-uploader` matured.
allowed-tools: >
  mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot,
  mcp__playwright__browser_click, mcp__playwright__browser_type,
  mcp__playwright__browser_fill_form, mcp__playwright__browser_press_key,
  mcp__playwright__browser_evaluate, mcp__playwright__browser_wait_for,
  mcp__playwright__browser_take_screenshot, mcp__playwright__browser_file_upload,
  mcp__Claude_in_Chrome__navigate, mcp__Claude_in_Chrome__javascript_tool,
  mcp__Claude_in_Chrome__find, mcp__Claude_in_Chrome__read_page,
  mcp__Claude_in_Chrome__list_connected_browsers,
  mcp__Claude_in_Chrome__tabs_context_mcp, mcp__Claude_in_Chrome__file_upload,
  Read, Bash
---

# Udemy Video Uploader

## Overview

Pushes rendered lecture `.mp4` files into existing Udemy lecture stubs as the
lecture's PRIMARY (Video) content type. This is the video-content sibling of
`udemy-resource-uploader` — same auth pattern, same `data-purpose` selector
strategy, same idempotency + safety rules — but it targets the lecture's
main content slot rather than the additive Resources sub-panel. Selectors
and per-step JS live in `playbook.md`.

This skill is the final mile of the per-lecture pipeline:

```
udemy-curriculum-populator (creates lecture stub)
        │
        ▼
udemy-lecture-video-renderer (produces lecture-X.Y.mp4 on disk)
        │
        ▼
udemy-video-uploader  ← THIS SKILL  (attaches the mp4 in the dashboard)
        │
        ▼
udemy-resource-uploader (attaches per-lecture cheat sheets, PDFs)
```

## When to use

- Lectures already exist in the curriculum dashboard (via
  `udemy-curriculum-populator`), and you have rendered MP4s on disk at
  `<course_root>/artifacts/lectures/lecture-X.Y.mp4`.
- You want to ship a batch of lectures (e.g. all of Section 2) without
  hand-uploading each one through the dashboard.
- You're re-running after a partial failure and want the skill to skip
  lectures that already have a video attached (idempotent default).
- You're replacing a previously-uploaded video with a newer render — pass
  `--force-replace` and confirm the destructive action when prompted.

## When NOT to use

- **Lecture stub doesn't exist yet** — run `udemy-curriculum-populator`
  first; this skill aborts if the planned `(section, lecture)` target is
  unresolved.
- **MP4 not yet rendered** — run `udemy-lecture-video-renderer` first; this
  skill aborts if the source file is missing.
- **Promotional video** (course-level intro video shown on the landing
  page) — out of scope here. That belongs to `udemy-landing-populator`
  (separate page, separate `data-purpose` for the promo video uploader).
- **Article body** — out of scope. Use the existing
  `udemy-curriculum-populator` Article-placeholder path when you want a
  text lecture.
- **Downloadable resources / cheat sheets** — use `udemy-resource-uploader`.
- **Reordering or deleting lectures** — out of scope. Additive-only by
  default; the only destructive action is `--force-replace` on an
  existing video and it requires explicit confirmation.
- **Publishing the course** — never. Always pauses for manual review.

## Prerequisites

1. **Lecture stub exists** in the dashboard (run
   `udemy-curriculum-populator` first if needed).
2. **MP4 exists on disk** at the resolved path (default
   `<course_root>/artifacts/lectures/lecture-X.Y.mp4`, overridable via
   `--mp4-dir`). The skill refuses to run if any planned MP4 is missing.
3. **Lecture's primary content type is unset OR is already Video.** This
   skill creates the Video content type if the lecture is a bare stub; if
   the lecture's primary content is Article (e.g. from the
   resource-uploader Article-placeholder workaround), the skill prompts to
   call `[data-purpose="replace-with-video"]` (destructive on Article body,
   non-destructive on attached Resources — Resources survive the swap).
4. **Authenticated Chrome MCP / Playwright session** — see the **Browser
   & authentication setup** section below. Identical setup to
   `udemy-resource-uploader`.

## Browser & authentication setup (READ BEFORE FIRST RUN)

Identical to `udemy-resource-uploader`. The skill drives a real browser at
`udemy.com/instructor/...` and cannot log in for you — establish an
authenticated session up front via one of:

### Option A — Chrome MCP (attaches to YOUR Chrome)

1. Open Chrome (your daily browser, with your Udemy login cookie).
2. Sign in to Udemy as the instructor account.
3. Keep at least one `udemy.com` tab open.
4. Ensure the Claude-in-Chrome extension is connected
   (`mcp__claude-in-chrome__list_connected_browsers` returns the right
   browser).
5. Invoke the skill. Every click + file-pick happens in the browser you can
   see.

### Option B — Playwright with a persisted profile

1. **First-time setup (one manual login):**
   ```bash
   npx playwright open --save-storage=~/.config/udemy-deployer/auth.json https://www.udemy.com/join/login-popup/
   ```
   Log in, close the window. Auth state persists.
2. **Subsequent runs:** the skill loads `auth.json` into a fresh Playwright
   context and arrives at the curriculum URL already logged in.
3. **When the cookie expires** (Udemy rotates ~every 30 days): re-run the
   step-1 command.

### What the skill does NOT do

- It does **not** prompt for or type credentials.
- It does **not** open a new browser if neither backend is set up — it
  aborts with the message "No authenticated Udemy session found. Run
  Option A or Option B setup, then retry."

## Input format

Primary input is per-lecture CLI flags rather than a YAML file (this skill
targets a small set of lectures per invocation, not a many-attachment
mapping). Two patterns:

```bash
# Single or comma-separated lectures
python upload.py --course-id 7140821 \
                 --course-root ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
                 --lectures 2.1,2.2,2.3

# Whole section (resolves to every "Lecture N.*" in section N from course-outline.md)
python upload.py --course-id 7140821 \
                 --course-root ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
                 --section 2
```

The MP4 path for `lecture-X.Y` is resolved as:

```
<course_root>/artifacts/lectures/lecture-X.Y.mp4
```

Overridable via `--mp4-dir <path>` (relative paths resolve against
`course_root`). The skill aborts before opening the browser if any planned
MP4 is missing.

## Invocation

Required:

| Flag | Purpose |
|---|---|
| `--course-id` | Numeric Udemy course id from the instructor URL (e.g. `7140821`) |
| `--course-root` | Absolute path to the course repo |
| One of `--lectures`, `--section`, or `--all` | Which lectures to upload |

Optional:

| Flag | Purpose |
|---|---|
| `--dry-run` / `--preview` | Print the action plan WITHOUT opening the browser |
| `--mp4-dir` | Override the MP4 directory (default `artifacts/lectures`) |
| `--force-replace` | Replace an existing video on a lecture (destructive — requires confirmation) |
| `--apply` | Used on a re-run when default is report-only; required to actually make changes |
| `--transcode-timeout` | Per-lecture max wait for Udemy transcoding (default 300s) |
| `--backend` | `chrome` (default) or `playwright` |

## Execution flow

Follow `playbook.md` for selectors and per-step JS. High-level:

1. **Preflight (no browser)**
   - Resolve the lecture list from `--lectures` / `--section` / `--all` by
     parsing `<course_root>/course-outline.md`.
   - For each planned lecture, resolve its MP4 path. ABORT if any is
     missing.
   - For each MP4, run `ffprobe`-style sanity checks (duration > 0,
     codec h264/aac, file size < 4GB Udemy hard limit, warn at >2GB).
   - Print the per-lecture plan tree:
     ```
     PLAN — would upload:
       Section 2 / Lecture 2.1 — "The Agentic Loop"
         file: artifacts/lectures/lecture-2.1.mp4 (87.4 MB, 9m 12s)
       Section 2 / Lecture 2.2 — "Prefilling"
         file: artifacts/lectures/lecture-2.2.mp4 (62.1 MB, 6m 48s)
     ```
   - **Pause for go-ahead before touching the browser.**

2. **Auth** — Chrome MCP `list_connected_browsers` OR Playwright
   `auth.json` (identical to `udemy-resource-uploader`).

3. **Navigate + verify login**
   - URL: `https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/`
   - Wait for `[data-purpose="curriculum-list"]` to be present.
   - If redirected to `/join/login-popup/`, ABORT.

4. **Resolve planned lectures to DOM nodes** using the same flat-DOM
   enumeration documented in `udemy-resource-uploader`'s playbook
   (sections + lectures are siblings under `curriculum-list`, not nested).
   ABORT if any target is unresolved.

5. **Per lecture — upload flow**

   For each `(lecture-target, mp4-path)`:

   a. **Idempotency check.** Read the lecture's current content state.
      - `[data-purpose="video-icon"]` present on the row → lecture has
        Video; SKIP unless `--force-replace`.
      - `[data-purpose="article-icon"]` present → Article main content; if
        the user passed `--force-replace`, prompt before swapping. If not,
        SKIP with a warning.
      - Neither → bare stub, proceed to (b).

   b. **Open the content panel.** Click
      `[data-purpose="lecture-add-content-btn"]`. Expect the `add-content`
      panel (bare stub) OR `edit-content` panel (has existing content).

   c. **Pick Video as primary content.**
      - Bare stub path: click `[data-purpose="select-video"]` in the
        `add-content` panel.
      - Replace path (`--force-replace`): click
        `[data-purpose="replace-with-video"]` in the `edit-content` panel,
        confirm any "this will replace your existing video" modal.

   d. **Locate the file input.** The video uploader exposes a hidden
      `<input type="file" name="file">` inside the video-uploader widget
      (selector TBD — likely `[data-purpose="video-uploader-input"]` or
      similar, mirroring `asset-uploader-input` for resources). Mark
      speculative selectors with `# TODO: verify` in code.

   e. **Attach the file.** Same multi-backend strategy as
      `udemy-resource-uploader` (Playwright `setInputFiles` preferred;
      Chrome MCP `file_upload` is sandboxed-off → fall back to
      `input.click()` via `javascript_tool` + user-driven OS picker).

   f. **Wait for upload + transcoding.** This is the key difference vs.
      resource uploads. Two distinct phases:
      - Upload: progress bar 0→100% (typically 5-60s on a fast link).
      - Transcoding: server-side, 30s-2min depending on length. The
        lecture row shows a "Processing" badge during transcode. The
        Save button is DISABLED until transcoding finishes.
      Poll until `[data-purpose="save-lecture"]` (or equivalent — TBD) is
      enabled. Hard timeout: `--transcode-timeout` (default 300s).

   g. **Save the lecture.** Click the Save button. Wait for the panel to
      close and the lecture row to show the video badge.

   h. **Verify.** Re-read the lecture row; confirm a `video-icon` /
      duration label is present. If not after timeout, ABORT with
      screenshot.

6. **Post-run report**
   - Per-lecture status table:
     `Section N / Lecture N.M / <mp4-filename> → UPLOADED | SKIPPED | REPLACED | FAILED`
   - Total bytes uploaded, total time elapsed.
   - Final screenshot of the curriculum page.

## Guardrails

- **Idempotent.** Default behaviour skips any lecture that already has a
  Video attached. `--force-replace` opts into destructive replacement and
  requires per-lecture confirmation.
- **Additive by default.** The only destructive operation is
  `--force-replace`, and it prompts before each replacement.
- **MP4 sanity checks.** Refuse to upload if duration is 0, file is empty,
  or file exceeds 4GB. Warn at >2GB (Udemy may reject in practice even
  though their stated limit is 4GB).
- **Selector-drift abort.** If any expected `data-purpose` selector
  returns zero matches, STOP, screenshot, log step + selector + URL. Do
  not silently try alternatives.
- **Lecture-target-missing abort.** If any planned lecture target cannot
  be resolved against the live curriculum, ABORT before uploading
  anything — never partial-apply.
- **Transcoding timeout.** Default 300s per lecture. On timeout,
  screenshot + abort; do NOT click Save while the Save button is still
  disabled (it's a no-op and creates user confusion).
- **Pause-and-confirm at >5 lectures per run.** Sanity check against
  runaway plans.
- **Never click Publish.** Never click Submit for Review. Never delete a
  lecture.
- **Never enter credentials.**

## Out of scope (v0 stub)

- Subtitles / captions upload (Udemy supports SRT/VTT — future v2).
- Re-ordering lectures.
- Setting per-lecture preview/free-preview flag.
- Promotional / landing-page video (belongs to `udemy-landing-populator`).
- Multi-language video tracks.

## Dry-run / preview mode

`--dry-run` (alias `--preview`) prints the full plan WITHOUT opening the
browser:

```
DRY RUN — udemy-video-uploader
Target: https://www.udemy.com/instructor/course/<course-id>/manage/curriculum/
Course root: ~/Documents/dev/udemy-courses/claude-architect-udemy-course
MP4 dir: artifacts/lectures
Backend: chrome

Resolved 3 lecture(s):
  Section 2 / Lecture 2.1 — "The Agentic Loop"
    file: artifacts/lectures/lecture-2.1.mp4 (87.4 MB, 9m 12s) ✓
  Section 2 / Lecture 2.2 — "Prefilling"
    file: artifacts/lectures/lecture-2.2.mp4 (62.1 MB, 6m 48s) ✓
  Section 2 / Lecture 2.3 — "Tool Use"
    file: artifacts/lectures/lecture-2.3.mp4 (—)              ✗ MISSING

File checks:
  ✗ 1 MP4 missing — fix before re-running

Per-lecture dashboard flow (would repeat for each found file):
  [a] Check lecture row for existing video-icon (idempotency)
  [b] Click [data-purpose="lecture-add-content-btn"]
  [c] Click [data-purpose="select-video"] (or replace-with-video if --force-replace)
  [d] Locate hidden <input type="file" name="file"> (TBD — verify on first run)
  [e] setInputFiles(<absolute path to MP4>)
  [f] Wait for upload + transcode complete (Save button enabled), 300s timeout
  [g] Click Save
  [h] Verify video-icon present on lecture row

To apply: fix missing files, then re-run without --dry-run.
```

## Verification

After a run, the user should see:

- ✅ Every planned lecture shows a video badge / duration label in the
  curriculum row.
- ✅ Re-running the skill (without `--force-replace`) reports zero drift
  (every planned lecture already has Video).
- ✅ No lecture title, resource attachment, or other lecture was modified.
- ✅ The Curriculum sidebar in the instructor nav still shows the
  in-progress state (no auto-publish).

Report success with a per-lecture table and a final screenshot path.

## Related skills

- `udemy-curriculum-populator` — runs FIRST; creates the lecture stubs
  this skill uploads into.
- `udemy-lecture-video-renderer` — runs IMMEDIATELY BEFORE; produces the
  MP4s this skill consumes from `<course_root>/artifacts/lectures/`.
- `udemy-resource-uploader` — closest sibling; same dashboard, same auth,
  same selector strategy, different content-type (additive resources vs.
  primary video).
- `udemy-coding-exercise-deployer` — sibling deployer for in-browser
  coding exercises (different lecture content type).
- `udemy-lecture-description-deployer` — sibling for per-lecture
  description text.
