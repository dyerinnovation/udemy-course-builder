---
name: udemy-resource-uploader
description: >
  Attach downloadable resources (PDF, .docx, etc.) to lectures in a Udemy
  course via Chrome MCP browser automation. Reads a YAML mapping of
  lecture-target → file-path and walks the
  `[data-purpose='lecture-add-content-btn']` → 'Resources' submenu flow per
  lecture. Idempotent (skips existing same-name attachments unless
  `--force`). Never publishes; never deletes; supports `--preview` dry-run
  mode. Use after `udemy-curriculum-populator` has created the lecture
  stubs and you need to ship per-lecture downloads (cheat sheets, study
  guides, sample code, etc.) without touching the lecture body.
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

# Udemy Resource Uploader

## Overview

Attaches downloadable resources (PDFs, .docx, sample-code archives, cheat
sheets, etc.) to existing lectures in a Udemy course's curriculum. This is
the resource-attachment sibling of `udemy-curriculum-populator` — same auth
pattern, same `data-purpose` selector strategy, same idempotency + safety
rules. Selectors and step sequences live in `playbook.md`.

This skill is purely **additive on resources** — it never touches the
lecture title, video, article body, content type, or any existing
attachments. The lecture must already exist (use
`udemy-curriculum-populator` first if it doesn't).

## When to use

- Curriculum scaffold is in place (sections + lectures exist) and you need
  to attach study guides, cheat sheets, sample code zips, or PDFs to one or
  more lectures.
- You want to mirror a `course-metadata/resources.yaml` mapping into the
  dashboard reproducibly across runs.
- You're re-running after a partial failure and want the skill to skip
  already-uploaded files (idempotent).

## When NOT to use

- **Lecture VIDEO upload** — out of scope (manual; needs separate skill if
  automated).
- **Inline images / video uploads inside an article body** — out of scope.
- **Reordering attachments** — out of scope. Order in the dashboard
  reflects upload order; if you need a specific order, delete + re-upload
  manually.
- **Deleting attachments** — never. The skill is additive only.
- **Section-level resources** — Udemy may not expose this at all; v1 is
  lecture-scoped only. Verify during recon if/when a request appears.
- **Publishing the course** — never. Always pauses for manual review.

## Prerequisites

1. **Lectures already exist** in the curriculum dashboard (run
   `udemy-curriculum-populator` first if needed).
2. **Each target lecture has a primary content type set** (Video or Article).
   This is a HARD Udemy gate: the `[data-purpose="add-resources-btn"]`
   button only appears in the lecture's `edit-content` panel AFTER the
   lecture's main content type is chosen. A bare lecture stub shows the
   `add-content` panel (Select content type — Video / Article / etc.)
   instead, with no Resources affordance. Workaround documented in the
   playbook: set the lecture as Article with a one-line placeholder, attach
   resources, then later replace the Article with the recorded Video — the
   resources stay attached through the Article→Video replacement.
3. **Local files exist** at the paths listed in the mapping. The skill
   refuses to run if any source file is missing.
4. **Authenticated Chrome MCP / Playwright session** — see the
   **Browser & authentication setup** section below.

## Browser & authentication setup (READ BEFORE FIRST RUN)

The skill drives a real browser at `udemy.com/instructor/...`. It cannot log
in for you — Udemy's anti-bot protections plus the no-credentials safety
rule make that explicit. **You must establish an authenticated session
before invoking this skill.** There are two supported backends; pick one up
front:

### Option A — Chrome MCP (attaches to YOUR Chrome)

This is the recommended path when you're at your own machine.

1. Open Chrome (your daily browser, with your Udemy login cookie).
2. Sign in to Udemy as the instructor account (e.g.
   `innovation@dyercapital.com`).
3. Open at least one tab on `udemy.com` — keeps the session warm.
4. Make sure the Claude-in-Chrome extension is connected (skill checks
   `mcp__claude-in-chrome__list_connected_browsers`). If not connected, the
   skill aborts with install instructions rather than silently failing.
5. Invoke the skill. It will use **your already-authenticated Chrome
   session** — every click + file-pick happens in the browser you can see.

Caveat: while the skill is driving Chrome, avoid using the same window
manually — competing input causes selector misses. Open a different
window/profile if you need to multitask.

### Option B — Playwright with a persisted profile

Use this when running headless, on a server, or you don't want the skill
touching your daily Chrome.

1. **First-time setup (one manual login):**
   ```bash
   npx playwright open --save-storage=~/.config/udemy-deployer/auth.json https://www.udemy.com/join/login-popup/
   ```
   Log in to Udemy in the window that opens. Close the window when the
   dashboard loads. The auth state (cookies + localStorage) is now
   persisted to `~/.config/udemy-deployer/auth.json`.
2. **Every subsequent run:** the skill loads that storage state into a
   fresh Playwright context, so the uploader arrives at
   `manage/curriculum/` already logged in. Playwright's `setInputFiles`
   handles the actual file pick.
3. **When the cookie expires** (Udemy rotates sessions ~every 30 days), the
   curriculum URL will redirect to login → skill aborts → re-run the
   step-1 command.

### What the skill does NOT do

- It does **not** prompt for or type credentials anywhere.
- It does **not** open a new browser if neither backend is set up — it
  aborts with the message "No authenticated Udemy session found. Run
  Option A or Option B setup, then retry."
- It does **not** save credentials to the repo or to the skill directory.

## Input format

Primary input: a YAML file at `course-metadata/resources.yaml` in the
course repo root.

```yaml
attachments:
  - section: 1
    lecture: 1.1   # required for lecture-level attachment
    files:
      - path: Claude-Created-Exam-Section-guides/CCA-CI-Study-Guide.pdf
        display_name: "Scenario 5: CI/CD Study Guide"
      - path: Claude-Created-Exam-Section-guides/CCA-Structured-Output-Study-Guide.pdf
        display_name: "Domain 4: Structured Output Study Guide"
  - section: 2
    lecture: 2.1
    files:
      - path: resources/cheat-sheets/agentic-loop-cheat-sheet.pdf
        # display_name omitted → falls back to filename minus extension
```

Field reference:

| Field | Required | Notes |
|---|---|---|
| `section` | yes | Numeric, matches `Section N:` in the dashboard |
| `lecture` | yes | Dotted form `N.M` matching the planned outline (resolved to per-section position 1..k for the dashboard) |
| `files[].path` | yes | Repo-relative or absolute. Skill aborts if missing. |
| `files[].display_name` | no | Override the visible name shown to students. Default: file basename minus extension. |

**Optional inline form:** instead of reading the YAML, the user may pass
the same structure as a parameter dict to the skill invocation. Useful for
ad-hoc one-off attachments.

## Invocation

The skill needs:

1. **Course ID** — numeric, from the instructor URL (e.g. `7140821`).
2. **Course repo path** — absolute path to the repo containing
   `course-metadata/resources.yaml`. Default:
   `/Users/jonathandyer/Documents/dev/udemy-courses/<course-slug>`.

Optional flags:

- `--preview` / `dryRun: true` — produce the full action plan as text
  WITHOUT opening the browser. User reviews, then re-invokes without the
  flag.
- `--sections=2,3,5` — only process attachments whose `section` matches the
  listed numbers.
- `--force` — re-upload even if a same-filename attachment already exists
  on the lecture (default behaviour: skip existing same-filename
  attachments to keep the run idempotent).
- `--apply` — used during a re-run; required to actually make changes when
  diff is non-empty.

## Execution flow

Follow `playbook.md` for every selector and JS snippet. High-level
sequence:

1. **Preflight (no browser)**
   - Verify `course-metadata/resources.yaml` exists (or the inline
     parameter dict was provided).
   - Parse the mapping. For every `files[].path`, resolve it against the
     course repo root. ABORT if any file is missing.
   - For each file, run a size check: warn (don't abort) if any file >
     50MB — Udemy may reject very large uploads; let the user decide.
   - Produce a per-attachment plan tree:
     ```
     PLAN — would attach:
       Section 1 / Lecture 1.1
         + CCA-CI-Study-Guide.pdf            → "Scenario 5: CI/CD Study Guide"
         + CCA-Structured-Output-Study-Guide.pdf → "Domain 4: Structured Output Study Guide"
       Section 2 / Lecture 2.1
         + agentic-loop-cheat-sheet.pdf      → "agentic-loop-cheat-sheet"
     ```
   - **Pause for go-ahead before touching the browser.**

2. **Auth**
   - Chrome MCP path: `list_connected_browsers` → expect the
     pre-authenticated browser. If multiple candidates, ASK the user.
   - Playwright path: load `~/.config/udemy-deployer/auth.json` into a
     fresh context. If file missing, ABORT with the Option B setup command.

3. **Navigate + verify login**
   - URL: `https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/`
   - Wait for `[data-purpose="curriculum-list"]` to be present.
   - If page redirected to `/join/login-popup/`, ABORT (auth setup
     pointer).

4. **Resolve every planned lecture target to a DOM node**
   - Use the playbook's flat-DOM enumeration (sections + lectures are
     siblings under `[data-purpose="curriculum-list"]`, not nested).
   - For each `attachments[i]`, find the `[data-purpose="lecture-editor"]`
     wrapper that belongs to `Section N` and is the M-th lecture under it.
   - If any lecture target is unresolved, ABORT and report the missing
     targets — user runs `udemy-curriculum-populator` first.

5. **Per attachment — flow per file**

   For each `(lecture-target, file)` in the plan:

   a. **Idempotency check.** Read the lecture's existing attachment list
      from `[data-purpose="downloadable-files-section"]` inside the
      lecture's `[data-purpose="edit-content"]` panel. Each attached file
      is a row text-line of shape `<filename>.<ext> (NNN.N kB)` with a
      `[data-purpose="delete-supplementary-asset-btn"]` sibling. If a
      resource with the same filename is already attached, SKIP this file
      unless `--force`. Log: `SKIP: <filename> already on Lecture N.M`.

   b. **Open the content panel.** Click
      `[data-purpose="lecture-add-content-btn"]` for that lecture. This
      toggles a sticky inline panel (same pattern as the section/lecture
      `+` pickers — Escape and outside-click do NOT close it; click the
      same button again to collapse, OR click
      `[data-purpose="content-tab-close"]`). Two panels are siblings:
      `add-content` (visible if no main content set yet — Video / Article
      pickers) and `edit-content` (visible if main content IS set — has
      Description / **Resources** / Lab buttons). The skill targets
      `edit-content`. **Pre-flight gate:** if `add-content` is visible
      instead of `edit-content`, the lecture has no primary content type;
      see Prerequisites #2 — set the lecture as Article with placeholder
      first, then re-run.

   c. **Click the Resources button.** Selector confirmed on first run:
      `[data-purpose="add-resources-btn"]` (NOT `resource-content-btn` as
      the v1 playbook guessed). Lives in the lecture's `edit-content`
      panel.

   d. **Locate the upload `<input type="file">`.** The Resources panel
      contains a tab strip (`[data-purpose="tab-nav-buttons"]`) with at
      least: "Downloadable File" (default), "External Resources", "Source
      Code". The Downloadable File tab is `tabpanel ref_160`-equivalent
      and contains a hidden `<input type="file" name="asset" class="ud-sr-only">`
      inside `[data-purpose="asset-uploader-input"]`. The visible "Select
      File" button is the same DOM node — labelled as a `button` in the
      AX tree but `type="file"`. There are TWO `input[type=file][name=asset]`
      in the DOM at any time (Downloadable File + Source Code tabs);
      always use the FIRST (Downloadable File). The Source Code one has
      `accept=".rb,.py,.sh"` — easy to filter on.

   e. **Attach the file.** **Important — file_upload primitives are often
      denied in real Chrome MCP sessions** (this skill's first apply run
      hit `code: -32000, message: "Not allowed"` on every
      `mcp__Claude_in_Chrome__file_upload` attempt regardless of file path
      or element ref). The reliable path is to **drive the page's UI
      directly** rather than the upload primitive:
      - **Preferred (Playwright path):** `browser_file_upload` with
        `setInputFiles` semantics works because Playwright owns the
        browser and bypasses the OS picker.
      - **Chrome MCP path (most users):** the `file_upload` primitive may
        be sandboxed off. Two options:
        1. **JS-click-input + native picker.** Find the
           `input[type="file"][name="asset"]` (the Downloadable File one)
           and call `.click()` on it via `javascript_tool`. The OS file
           picker opens. The user picks the file. Claude continues with
           the verification step. Hybrid — Claude drives every other
           click, user only handles the picker dialog. Multi-file: the
           input has `multiple="false"`, so one file per click.
        2. **Drag-and-drop.** The Resources panel accepts file drops onto
           the upload zone (Uppy widget convention). Claude prompts the
           user to drag N PDFs from Finder onto the zone; Udemy uploads
           them in parallel. Multi-file friendly, single user gesture.
      - **Do NOT silently retry `file_upload` after a "Not allowed"
        response** — surface the limitation to the user and let them
        choose JS-click vs drag-drop.

   f. **Wait for upload completion.** Poll
      `[data-purpose="downloadable-files-section"]`'s text content for
      the new filename to appear without a `(Processing)` suffix. Hard
      timeout: 120s per file. Big files (>5MB) may briefly show
      `(Processing)` while Udemy server-side-processes them — that's
      normal; wait for the kB suffix.

   g. **Set display name (optional).** Uploaded filenames render verbatim
      in the dashboard; Udemy does not expose an inline rename for
      Downloadable File assets at v1. If `display_name` is provided in
      the YAML, the v1 skill records it in the run report but takes no
      dashboard action. Workaround: rename the source file on disk to
      the desired display name BEFORE upload (Udemy preserves the
      filename verbatim). For v2: explore whether Udemy's REST API
      exposes `PATCH /lecture/<id>/asset/<id>` for rename.

   h. **Verify.** Re-read `[data-purpose="downloadable-files-section"]`;
      confirm the new filename is present (and not in `(Processing)`
      state). If not after timeout, ABORT with screenshot.

6. **Post-run report**
   - Per-attachment status table:
     `Section N / Lecture N.M / <filename> → UPLOADED | SKIPPED | FAILED`
   - Total bytes uploaded, total time elapsed.
   - Final screenshot of the curriculum page.

## Guardrails

- **Idempotent.** Default behaviour skips any same-filename attachment
  already present on the target lecture. `--force` re-uploads (Udemy
  permits multiple attachments with the same filename — both will appear).
- **Additive only.** Never deletes an existing attachment. Never reorders.
  If the user wants something removed, they do it manually.
- **Selector-drift abort.** If any expected `data-purpose` selector
  returns zero matches, STOP, screenshot, log step + selector + URL.
  Don't try alternatives silently.
- **Lecture-target-missing abort.** If any planned lecture target cannot
  be resolved against the live curriculum, ABORT before uploading
  anything — never partial-apply.
- **File-size sanity check.** Warn (don't abort) on any file > 50MB.
  Udemy may reject; let the user decide whether to proceed.
- **Upload timeout.** 120s per file. On timeout, screenshot + abort —
  don't retry blindly (Udemy may have accepted the upload but the
  indicator is stale).
- **Pause-and-confirm at >10 attachments per run.** Sanity check against
  runaway YAML.
- **Never click Publish.** Never click Submit for Review. Never click any
  delete button (resource row delete OR lecture-level delete).
- **Never enter credentials.**

## Out of scope (v1)

- Section-level resources (verify support during recon; if Udemy supports
  it, add in v2).
- Inline images / video uploads inside article-body lectures.
- Reordering attachments after upload.
- Resource deletion or rename of pre-existing attachments.
- External-resource URLs (download link to a hosted file vs. uploaded
  file) — `add-external-resource-btn` may exist; out of scope for v1.

## Dry-run / preview mode

When invoked with `--preview` or `dryRun: true`, produce the complete
action plan as text WITHOUT opening the browser:

```
DRY RUN — udemy-resource-uploader
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course
Source: course-metadata/resources.yaml

Parsed plan (3 attachments across 2 lectures):
  Section 1 / Lecture 1.1
    + CCA-CI-Study-Guide.pdf (482 KB)            → "Scenario 5: CI/CD Study Guide"
    + CCA-Structured-Output-Study-Guide.pdf (1.1 MB) → "Domain 4: Structured Output Study Guide"
  Section 2 / Lecture 2.1
    + agentic-loop-cheat-sheet.pdf (212 KB)      → "agentic-loop-cheat-sheet"

File checks:
  ✓ All 3 source files exist
  ✓ No file exceeds 50MB threshold

Per-attachment dashboard flow (repeated for each file):
  [a] Read lecture attachment list (idempotency)
  [b] Click [data-purpose="lecture-add-content-btn"] on the target lecture
  [c] Click "Resources" sub-option (selector TBD — first run captures)
  [d] Locate hidden file input (TBD)
  [e] setInputFiles(<absolute path>)
  [f] Wait for upload-complete indicator (TBD), 120s timeout
  [g] If display_name provided: set rename input + save (TBD)
  [h] Verify new attachment row present

Total to upload: 3 files (1.8 MB)
Existing attachments that would be SKIPPED: 0 (full read happens at apply time)

To apply: re-run without --preview AND with --apply
```

## Verification

After a run, the user should see:

- ✅ Every planned `(lecture, file)` appears in the lecture's resource
  list with the correct display name.
- ✅ Re-running the skill (without `--apply`) reports zero drift (every
  planned attachment matches an existing same-filename attachment).
- ✅ No lecture title, video, body, or other attachment was modified.
- ✅ The Curriculum sidebar in the instructor nav still shows the
  in-progress state (no green checkmark unless other criteria are met).

Report success with a per-attachment table and a final screenshot path.

## Related skills

- `udemy-curriculum-populator` — runs FIRST; creates the lecture stubs
  this skill attaches files to.
- `udemy-coding-exercise-deployer` — sibling deployer for in-browser
  coding exercises (different content type, same dashboard pattern).
- `udemy-landing-populator` — sibling deployer for landing/goals/messages.
- `udemy-lecture-writer` — produces lecture-script content (separate from
  pushing downloads into the dashboard).
