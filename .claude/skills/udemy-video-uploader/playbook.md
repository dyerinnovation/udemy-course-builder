# udemy-video-uploader — Playbook

Operating reference for the `[data-purpose="lecture-add-content-btn"]` →
"Video" picker → file-upload → transcode-wait → save flow. Inherits the
curriculum DOM model + `data-purpose` strategy from
`udemy-curriculum-populator` and `udemy-resource-uploader`. Video-specific
selectors marked `TBD` / `# TODO: verify` will be confirmed on the first
real `--apply` run; do not assume them.

## URL

```
https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/
```

Numeric instructor course id, NOT the public slug. Read from the URL
while logged in to the instructor dashboard.

## DOM model — sections + lectures are siblings, not nested

Inherited verbatim from `udemy-resource-uploader/playbook.md`. Every
curriculum item (section row OR lecture row) is a direct child of
`[data-purpose="curriculum-list"]`. Use the enumeration JS in that
playbook to walk wrappers and resolve "Section N / Lecture M" to a
`[data-purpose="lecture-editor"]` wrapper. Keep the wrapper reference so
all subsequent queries scope to one lecture.

## Confirmed selectors (from sibling skills)

Inherited from `udemy-resource-uploader/playbook.md` and
`udemy-curriculum-populator/playbook.md`. Do not re-verify — these are
known good.

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A lecture row | `[data-purpose="lecture-editor"]` |
| Lecture title text | `[data-purpose="item-full-title"]` |
| Lecture index label ("Lecture N:") | `[data-purpose="item-object-index"]` |
| Toggle the lecture content panel | `[data-purpose="lecture-add-content-btn"]` |
| Close the open panel | `[data-purpose="content-tab-close"]` |
| `add-content` panel wrapper (no main content set) | `[data-purpose="add-content"]` |
| `edit-content` panel wrapper (main content set) | `[data-purpose="edit-content"]` |
| Pick Video as primary content | `[data-purpose="select-video"]` |
| Pick Video Mashup | `[data-purpose="select-videomashup"]` |
| Pick Article | `[data-purpose="select-article"]` |
| Replace primary content with Video | `[data-purpose="replace-with-video"]` |
| Article main-content indicator on lecture row | `[data-purpose="article-icon"]` |

## Video-uploader selectors — TBD (verify on first --apply run)

These are the BEST GUESSES extrapolated from the resource-uploader's
selector family. Mark anything not yet confirmed with `# TODO: verify`
in code and update this table after the first live run.

| Purpose | Best-guess selector | Status |
|---|---|---|
| Video-uploader widget wrapper | `[data-purpose="video-uploader-input"]` | TODO: verify (analogous to `asset-uploader-input` for resources) |
| Hidden file input | `input[type="file"][name="file"]` (or `name="video"`) inside the wrapper, likely with `accept="video/*"` or comma-list including `.mp4,.mov` | TODO: verify name attr + accept |
| Upload progress bar | `[data-purpose="upload-progress"]` or class containing `progress` | TODO: verify |
| "Processing" / transcoding badge on lecture row | `[data-purpose="processing-status"]` or text "Processing" inside the row | TODO: verify |
| Save button in the video panel | `[data-purpose="save-lecture"]` OR `[data-purpose="content-tab-save"]` OR a plain `<button>` with text "Save" | TODO: verify — try the three in that order |
| Video icon on lecture row (lecture has Video) | `[data-purpose="video-icon"]` | TODO: verify (mirrors confirmed `article-icon`) |
| Duration label on lecture row | `[data-purpose="lecture-duration"]` or text matching `\d+min` | TODO: verify |
| "Replace existing video" confirmation modal | `[role="dialog"]` + button text "Replace" | TODO: verify |

## Pre-flight: which path is this lecture on?

Before opening the content panel for an upload, classify the lecture:

```js
function lectureState(lectureWrapper) {
  return {
    hasVideo:   !!lectureWrapper.querySelector('[data-purpose="video-icon"]'),    // TODO: verify selector
    hasArticle: !!lectureWrapper.querySelector('[data-purpose="article-icon"]'),  // CONFIRMED
    duration:   lectureWrapper.querySelector('[data-purpose="lecture-duration"]')?.innerText?.trim() // TODO: verify selector
  };
}
```

Decisions per state:

| State | Default (no `--force-replace`) | With `--force-replace` |
|---|---|---|
| Bare stub (neither) | UPLOAD via `select-video` | UPLOAD via `select-video` |
| Has Article | SKIP with warning ("Article lecture; replace would discard the body. Re-run with --force-replace to swap to Video.") | Open `edit-content` → click `replace-with-video` → confirm modal → UPLOAD |
| Has Video | SKIP ("Lecture already has Video.") | Open `edit-content` → click `replace-with-video` → confirm modal → UPLOAD |

The Article-to-Video swap PRESERVES any attached resources (Resources
sub-panel is separate from primary content type) — see
`udemy-resource-uploader/playbook.md` line "Article main-content does NOT
block a later Video upload". The Video-to-Video replace DOES discard the
existing video (that's the point of `--force-replace`).

## Per-lecture upload flow

1. **Locate wrapper.** Enumerate `curriculum-list` per the sibling
   playbook; find the `[data-purpose="lecture-editor"]` wrapper whose
   `item-object-index` matches `Lecture <index_in_section>` under the
   matching `section-editor`.

2. **Idempotency / state classification** (above). SKIP per the table
   unless `--force-replace`.

3. **Open content panel.** Click `[data-purpose="lecture-add-content-btn"]`
   in the lecture wrapper. Expect either `add-content` or `edit-content`
   to become visible (`offsetParent !== null`).

4. **Pick Video.**
   - **Bare stub path:** `[data-purpose="select-video"]` in the
     `add-content` panel. The panel re-renders to expose the video
     uploader UI.
   - **Replace path (`--force-replace`):**
     `[data-purpose="replace-with-video"]` in the `edit-content` panel.
     A confirmation modal MAY appear ("Replace existing video?"). Click
     the modal's Replace button. **Only proceed if the user has
     explicitly confirmed this run.** Don't silently click destructive
     buttons.

5. **Locate the file input.** Inside the lecture wrapper, find the
   video file input — best guess:

   ```js
   const inputs = Array.from(
     lectureWrapper.querySelectorAll('input[type="file"]')
   );
   // TODO: verify the right disambiguator. Candidates:
   //   - name="file" or name="video"
   //   - accept includes "video/*" or ".mp4"
   //   - parent has [data-purpose="video-uploader-input"]
   const videoInput = inputs.find(i =>
     /video/.test(i.accept || "") || /\.mp4/i.test(i.accept || "")
   );
   ```

   If you also see the `asset-uploader-input` (resources) input in the
   wrapper, filter it out — its `accept` is empty.

6. **Attach the file.** Backend-specific (same as
   `udemy-resource-uploader/playbook.md` — `Claude_in_Chrome.file_upload`
   is sandboxed off):
   - **Playwright:** `mcp__playwright__browser_file_upload` with the
     absolute MP4 path and the input's snapshot ref. Bypasses OS picker.
   - **Chrome MCP:**
     - Preferred for video: JS-click the hidden `<input>` via
       `mcp__Claude_in_Chrome__javascript_tool`; user picks the file in
       the native OS dialog.
     - Drag-drop works (Uppy widget convention) but is less ergonomic
       for one file at a time. Use if the user prefers it.

7. **Wait for upload + transcode.** TWO phases — this is the key
   difference vs. resource uploads.

   **Phase 1 — Upload (5-60s typical).**
   Poll the upload progress indicator. Watch for any of:
   - `[data-purpose="upload-progress"]` value → 100 (TODO: verify
     selector + attribute)
   - Text "Upload complete" / "Uploaded" appearing in the panel
   - Progress bar element disappearing
   Fail-safe timeout for upload only: 120s (separate from transcode).

   **Phase 2 — Transcode (30s-2min typical; up to several minutes for
   long lectures).**
   After upload, Udemy starts server-side transcoding. The lecture row
   typically shows a "Processing" badge during this phase. The Save
   button is DISABLED until transcoding finishes.

   ```js
   function pollUntilSaveEnabled(panelRoot, timeoutMs) {
     const start = Date.now();
     return new Promise((resolve, reject) => {
       const tick = () => {
         // TODO: verify Save selector — try in order:
         //   [data-purpose="save-lecture"], [data-purpose="content-tab-save"],
         //   then fall back to button:contains("Save").
         const btn = panelRoot.querySelector('[data-purpose="save-lecture"]')
                  || panelRoot.querySelector('[data-purpose="content-tab-save"]')
                  || Array.from(panelRoot.querySelectorAll('button'))
                          .find(b => b.innerText.trim() === 'Save');
         if (btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true') {
           return resolve(btn);
         }
         if (Date.now() - start > timeoutMs) {
           return reject(new Error('Save did not enable within timeout'));
         }
         setTimeout(tick, 2000);
       };
       tick();
     });
   }
   ```

   Default total timeout (upload + transcode): 300s (overridable via
   `--transcode-timeout`).

   **Do NOT click Save while disabled** — it's a no-op and creates user
   confusion ("I clicked Save but nothing happened"). Wait for the
   enabled state explicitly.

8. **Save.** Click the Save button. The panel collapses; the lecture row
   updates to show:
   - Video icon (TODO: verify — likely `[data-purpose="video-icon"]`)
   - Duration label (e.g. "9:12")
   Wait for at least the duration text to appear before considering the
   upload "done".

9. **Verify.** Re-enumerate the lecture row state:
   - `hasVideo === true`
   - `duration` is non-empty
   - No `[role="alert"]` red banner
   If verification fails after a short retry window (10s), screenshot
   and abort that lecture as `FAILED` — but continue to the next lecture
   (per-lecture failure should not halt the whole batch unless something
   structural broke, like the curriculum page going stale).

## Known gotchas

### Transcode wait time

Lecture videos are NOT instantly available after upload. The Save button
remains disabled until Udemy finishes server-side transcoding, which
takes:

- ~30s for short lectures (<3 min)
- 60-120s for mid-length lectures (3-10 min)
- Up to several minutes for long lectures (>20 min)

Plan for this when batching: a 10-lecture run at 90s transcode each is
~15 minutes of wall-clock time even on instant uploads. Provide a
progress log per lecture so the user knows the run isn't hung.

### File size

- **Stated limit:** 4 GB per video file (Udemy docs).
- **Practical wobble:** uploads >2 GB sometimes stall or fail with no
  clear error in the UI. The skill warns at 2 GB and refuses at 4 GB.
- **Rendered course videos** from `udemy-lecture-video-renderer` are
  typically 30-100 MB for 5-15 min lectures (h264 + AAC at slidev
  resolutions) — well clear of either limit.

### Promotional Video vs Lecture Video

The course also has a **Promotional Video** uploader on the landing-page
edit screen (`/manage/goals/` or `/manage/basics/`). That's a SEPARATE
flow with different selectors and belongs to `udemy-landing-populator`.
**This skill never touches the promo video.** If you accidentally
navigate to `/manage/basics/` instead of `/manage/curriculum/`, the
curriculum-list selector will not appear and the skill will abort —
that's the intended safety.

### Lecture already has a video

Default: SKIP with a clear "already has Video" log line. Re-running the
skill is therefore safe across iterations of `udemy-lecture-video-renderer`
as long as the rendered file has the same name on disk — the skill
will skip rather than uploading a duplicate.

To replace an existing video (e.g. after re-render with corrections):
pass `--force-replace`. The skill will:
1. Prompt for confirmation before each replacement.
2. Open the `edit-content` panel.
3. Click `[data-purpose="replace-with-video"]`.
4. Handle any confirmation modal.
5. Run the normal upload flow.

The replacement DISCARDS the old video file from Udemy. It does NOT
touch attached resources (those live in a separate sub-panel).

### Article-to-Video swap

If a lecture has Article main content (e.g. from the resource-uploader
Article-placeholder workaround), `--force-replace` will swap it to
Video. The article body is DISCARDED in this swap. Attached resources
SURVIVE (confirmed in `udemy-resource-uploader/playbook.md`).

The skill prompts before this destructive action.

### Save button: never click while disabled

The Save button in the video panel disables itself in three situations:
1. No file selected yet (pre-upload).
2. Upload in progress (the 0→100% phase).
3. Server transcoding in progress (the "Processing" phase after upload).

Always poll until `disabled === false` AND `aria-disabled !== 'true'`
before clicking. Clicking while disabled is a no-op but it's hard to
debug because the panel doesn't visibly react.

## Verifying upload success

After Save closes the panel, the lecture row in the curriculum list
should show:

1. **Video badge / icon** — `[data-purpose="video-icon"]` # TODO: verify
2. **Duration label** — `\d+min` or `\d+:\d+` text on the row
3. **No "Processing" badge** — that should be gone once Save was enabled
4. **No `[role="alert"]` red banner** — anywhere on the page

A complete success log line for one lecture:

```
UPLOADED Section 2 / Lecture 2.1 — "The Agentic Loop"
  file: lecture-2.1.mp4 (87.4 MB)
  upload: 14s   transcode: 67s   save: 1s   total: 82s
  verified: video-icon present, duration "9:12"
```

## Recovery — what to clean up if a run dies mid-flow

The skill is per-lecture atomic — if it dies after the file upload
started but before Save, the lecture state on Udemy depends on where it
died:

| Died after... | Lecture state | Recovery |
|---|---|---|
| `lecture-add-content-btn` opened the panel | Stub unchanged | Re-run; the skill re-opens the panel cleanly. Or manually click `[data-purpose="content-tab-close"]` to dismiss. |
| `select-video` clicked but no file uploaded | Lecture is in "uploader showing" state but no video. Looks like an open panel with an empty uploader. | Re-run; the panel is sticky and will accept a fresh file pick. Or manually close + reopen. |
| File picked, mid-upload | The upload either succeeds (Udemy will have the file but no Save was clicked) or fails (no file). Refresh the curriculum page — if a "Processing" badge appears on the row but no Save was clicked, the panel state is recoverable by re-opening the lecture and clicking Save manually. | Re-open the lecture panel in the dashboard; if you see a video preview + Save button, click Save manually. If the panel is empty, re-run the skill. |
| Upload complete, transcode running, skill timed out | Udemy has the file; transcode will finish whether the skill is watching or not. After the skill exits, wait a minute, refresh the curriculum, open the lecture, click Save. | Manual Save in the dashboard, OR re-run with `--force-replace` if you want the skill to redo it cleanly. |
| Save clicked but verification failed | Video probably IS saved; the verification selector just couldn't find the icon (selector drift). | Manual eyeball check of the row. If the duration label appears, you're done. Update the `video-icon` selector in this playbook and re-run. |

**Never click the lecture-delete button as part of recovery** — that
loses the lecture stub itself. The skill never deletes; the operator
shouldn't either unless explicitly intended.

## First-run capture protocol

When you run `--apply` for the first time, capture the following and
update this playbook:

1. The actual `data-purpose` value of the video-uploader widget wrapper.
2. The actual `name` + `accept` attributes of the hidden file input.
3. The actual selector for the upload progress indicator.
4. The actual selector for the "Processing" / transcoding badge.
5. The actual selector for the Save button.
6. The actual `data-purpose` of the video-icon on the row.
7. Sample timings: upload duration + transcode duration for a 10-minute
   lecture rendered at slidev resolution.

Once these are in the "Confirmed selectors" table above, future runs are
fully automated.
