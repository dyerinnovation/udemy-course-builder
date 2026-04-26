---
name: udemy-lecture-description-deployer
description: >
  Deploy lecture descriptions from `course-metadata/lecture-descriptions.yaml`
  into the matching lecture's Description field in the Udemy dashboard via
  Chrome MCP. Walks the `[data-purpose='lecture-add-content-btn']` →
  'Description' submenu flow per lecture, fills the textarea using the React
  value-setter pattern, and saves. Idempotent (skips lectures whose
  description matches the YAML; `--force` to overwrite). Never publishes;
  supports `--preview` dry-run mode.
allowed-tools: >
  mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot,
  mcp__playwright__browser_click, mcp__playwright__browser_type,
  mcp__playwright__browser_fill_form, mcp__playwright__browser_press_key,
  mcp__playwright__browser_evaluate, mcp__playwright__browser_wait_for,
  mcp__playwright__browser_take_screenshot, mcp__Claude_in_Chrome__navigate,
  mcp__Claude_in_Chrome__javascript_tool, mcp__Claude_in_Chrome__find,
  mcp__Claude_in_Chrome__read_page, mcp__Claude_in_Chrome__list_connected_browsers,
  mcp__Claude_in_Chrome__tabs_context_mcp, Read, Bash
---

# Udemy Lecture Description Deployer

## Overview

Pushes per-lecture description text from `course-metadata/lecture-descriptions.yaml`
into the matching lecture's Description field in the Udemy instructor
dashboard. Sibling to `udemy-lecture-description-writer` (which authors the
YAML — it does NOT deploy). Same auth, idempotency, and selector-drift
guardrails as `udemy-curriculum-populator` and
`udemy-coding-exercise-deployer`. Selectors and JS snippets live in
`playbook.md`.

The dashboard flow per lecture: click the lecture's
`[data-purpose="lecture-add-content-btn"]` to open the content-type picker,
pick the "Description" sub-option, fill the textarea using the React
value-setter pattern, click Save. Then verify the saved description matches
the YAML.

## When to use

- The course already has lectures created (via `udemy-curriculum-populator`)
  and the per-lecture description YAML is finalized.
- You want to bulk-push descriptions for an entire section, or for the whole
  course, in one run.
- You want to verify the dashboard descriptions match the YAML (idempotent
  re-run reports drift but doesn't change anything unless `--force`).

## When NOT to use

- **Authoring the descriptions** — that's `udemy-lecture-description-writer`.
- **Article-type lecture body content** (text-only lectures with no video) —
  out of scope (different submenu path; would extend this skill or fork).
- **Inline images / formatted text in descriptions** — out of scope; v1 is
  plain text only.
- **Description deletion** — never. Skill is additive/overwrite-only.
- **Lecture stub creation** — must already exist. Run
  `udemy-curriculum-populator` first.
- **Publishing the course** — never.

## Prerequisites

1. **Lectures already exist** in the dashboard for every YAML key. Run
   `udemy-curriculum-populator` first if not.
2. **`course-metadata/lecture-descriptions.yaml` exists** in the course repo
   (produced by `udemy-lecture-description-writer`). Format:
   ```yaml
   "2.1":
     description: "Walk through the agentic loop end-to-end..."
   "2.2":
     description: "Why prefilling matters and when to reach for it..."
   ```
   Keys are the dotted lecture numbers from `course-outline.md` (`Section.Lecture`).
3. **Authenticated Chrome MCP (or Playwright) session** — see
   **Browser & authentication setup** below.

## Browser & authentication setup (READ BEFORE FIRST RUN)

The skill drives a real browser at `udemy.com/instructor/...`. It cannot log
in for you — Udemy's anti-bot protections plus the no-credentials safety rule
make that explicit. **You must establish an authenticated session before
invoking this skill.** There are two supported backends; pick one up front:

### Option A — Chrome MCP (attaches to YOUR Chrome)

This is the recommended path when you're at your own machine.

1. Open Chrome (your daily browser, with your Udemy login cookie).
2. Sign in to Udemy as the instructor account (e.g. `innovation@dyercapital.com`).
3. Open at least one tab on `udemy.com` — keeps the session warm.
4. Make sure the Claude-in-Chrome extension is connected (skill checks
   `mcp__claude-in-chrome__list_connected_browsers`). If not connected, the
   skill aborts with install instructions rather than silently failing.
5. Invoke the skill. It will use **your already-authenticated Chrome
   session** — every click happens in the browser you can see.

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
   dashboard loads. The auth state (cookies + localStorage) is now persisted
   to `~/.config/udemy-deployer/auth.json`.
2. **Every subsequent run:** the skill loads that storage state into a fresh
   Playwright context, so the deployer arrives at `manage/curriculum/`
   already logged in.
3. **When the cookie expires** (Udemy rotates sessions ~every 30 days), the
   navigation step will redirect to login → skill aborts → re-run the step-1
   command.

### What the skill does NOT do

- It does **not** prompt for or type credentials anywhere.
- It does **not** open a new browser if neither backend is set up — it
  aborts with the message "No authenticated Udemy session found. Run Option
  A or Option B setup, then retry."
- It does **not** save credentials to the repo or to the skill directory.

## Invocation

The skill needs:

1. **Course ID** — numeric, from the instructor URL. E.g. `7140821`.
2. **Course repo path** — absolute path to the repo containing
   `course-metadata/lecture-descriptions.yaml`.

Optional:

- **YAML path** — defaults to `<repo>/course-metadata/lecture-descriptions.yaml`.
  Override with `--yaml-path=<path>` or pass an inline mapping.
- `--preview` / `dryRun: true` — produce the action plan as text WITHOUT
  opening the browser. Diff vs current dashboard state.
- `--lectures=2.1,2.2,3.5` — only deploy the listed lecture numbers.
- `--sections=2,3` — only deploy lectures whose key starts with the listed
  section numbers.
- `--force` — overwrite even when the dashboard description already matches
  the YAML (or when the dashboard has a non-empty different description).
  Without this flag, an existing non-matching description triggers a prompt.

## Execution flow

Follow `playbook.md` for every selector and JS snippet. High-level sequence:

1. **Preflight (no browser)**
   - Verify `course-metadata/lecture-descriptions.yaml` exists.
   - Parse it: `{ "2.1": {description: "..."}, "2.2": {...}, ... }`.
   - Validate every key matches `^\d+\.\d+$`.
   - Validate every `description` is plain text (no HTML/markdown image
     syntax in v1).
   - Report the parsed plan back to the user as a list of lecture-key →
     description-length pairs. **Pause for go-ahead before touching the
     browser.**

2. **Auth**
   - Chrome MCP path: `list_connected_browsers` → expect the
     pre-authenticated browser. If multiple candidates, ASK the user to
     pick.
   - Playwright path: load `~/.config/udemy-deployer/auth.json` into a fresh
     context. If file missing, ABORT with the Option B setup command.

3. **Navigate + verify login**
   - URL: `https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/`
   - Wait for `[data-purpose="curriculum-list"]` to be present.
   - If page redirected to `/join/login-popup/`, ABORT (auth setup pointer).

4. **Read existing curriculum** — enumerate every section + lecture wrapper
   under `[data-purpose="curriculum-list"]` using the FLAT-DOM enumeration
   in `playbook.md` (sections + lectures are SIBLINGS, not nested). Record
   each lecture's wrapper element handle keyed by dotted number
   (`Section.Position-within-section`).

5. **Read existing descriptions (idempotency baseline)**
   - For each YAML key, locate the lecture wrapper. If absent, mark as
     `MISSING` (skill cannot create lectures — that's the populator).
   - Read the lecture's current description from the DOM (selector TBD —
     capture on first `--apply` run; likely a content-summary node inside
     the lecture's expanded edit area).
   - Reconcile vs YAML:
     - Identical (whitespace-trimmed) → mark `MATCH` (skip unless `--force`).
     - Empty in dashboard → mark `CREATE`.
     - Non-empty + different → mark `OVERWRITE` (only proceeds if `--force`;
       otherwise prompt or skip).
   - Print the diff. If invoked WITHOUT `--force` AND any `OVERWRITE` exist,
     STOP and surface the diff with instructions to re-run with `--force`
     for those entries.

6. **Pause-and-confirm threshold**
   - If the plan would write **more than 20 descriptions** in one run,
     pause after the first 5 and ask the user to verify the first batch
     looks correct in the dashboard before proceeding. Sanity check against
     YAML parsing errors or selector drift on a small sample first.

7. **Apply (per lecture)**
   - Per lecture in YAML order:
     1. Click `[data-purpose="lecture-add-content-btn"]` for that lecture
        (toggles content-type picker — sticky-inline pattern, NOT a
        popover; same toggle behaviour as `add-item-inline`).
     2. Click the "Description" sub-option (selector TBD — capture on first
        `--apply` run via the selector-drift handler).
     3. Locate the description textarea (TBD selector; likely a `<textarea>`
        inside a `[data-purpose="description-form"]` wrapper based on Udemy's
        naming pattern).
     4. **Fill using the React value-setter pattern** (Udemy's React inputs
        ignore `input.value = x`):
        ```js
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(textarea, descriptionText);
        textarea.dispatchEvent(new Event('input', {bubbles: true}));
        textarea.dispatchEvent(new Event('change', {bubbles: true}));
        ```
     5. Click Save (TBD selector — likely
        `[data-purpose="submit-description-form"]`).
     6. Wait for the form to disappear AND for the description to appear in
        the lecture's metadata row (re-read DOM).
     7. Verify the persisted text matches the YAML byte-for-byte (after
        trimming). If mismatched, screenshot + ABORT (don't power through —
        could be a Udemy character-limit rejection or selector drift on the
        save).

8. **Verify + report**
   - Re-enumerate the curriculum and per-lecture descriptions.
   - Print a per-lecture table: `Lecture N.M → CREATED | OVERWROTE | MATCHED | SKIPPED | FAILED`.
   - Take a final screenshot of the curriculum page.

## Safety rules

- **NEVER publish.** Save only. The user controls publishing.
- **NEVER delete a description.** Skill is additive/overwrite-only. If the
  YAML lacks a key for a lecture that has a description, the existing
  description is left alone.
- **NEVER enter credentials.**
- **NEVER reorder, rename, or otherwise mutate a lecture beyond the
  Description field.**
- **Idempotent.** Default behaviour skips any lecture whose dashboard
  description already matches the YAML. `--force` is required to overwrite a
  divergent existing description.
- **Pause-and-confirm at >20 descriptions per run.** Stop after the first 5
  and ask the user to spot-check before continuing — sanity check against
  parsing errors, selector drift, or Udemy length-limit rejections.
- **Selector-drift abort.** If any expected `data-purpose` selector returns
  zero matches, STOP, screenshot to `/tmp/udemy-desc-drift-<timestamp>.png`,
  log step + selector + URL. Don't try alternative selectors silently.
- **Validation error abort.** If Udemy returns a red banner / `[role="alert"]`
  on save (e.g. exceeded character limit), STOP, screenshot, report. Do NOT
  retry.
- **Verify after save.** Always re-read the persisted description and confirm
  byte-for-byte match (trimmed). Mismatch = ABORT — don't continue blindly.
- **Login redirect = ABORT** with the matching backend setup pointer (Option
  A or B from the auth section above).

## Out of scope (v1)

- **Article-type lectures** (text-only, no video). The "Description" sub-flow
  here targets a video lecture's metadata Description, not the Article body
  editor. Article body would extend this skill or fork.
- **Inline images, links, or formatted text** in descriptions. Plain text
  only. The textarea is a single `<textarea>`, not a rich-text editor — but
  validate plain-text-only on input as a guard.
- **Description deletion or clearing.** No empty-string overwrites.
- **Bulk import from CSV / spreadsheets.** YAML is the only input format.
- **Cross-course bulk pushes.** One course id per invocation.
- **Re-uploading lecture video, slides, captions, transcripts.**

## Dry-run / preview mode

When invoked with `--preview`, produce the full action plan as text WITHOUT
opening the browser:

```
DRY RUN — udemy-lecture-description-deployer
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
YAML: /Users/jonathandyer/Documents/dev/udemy-courses/claude-architect-udemy-course/course-metadata/lecture-descriptions.yaml

Parsed plan from YAML (3 lectures):
  2.1 The Agentic Loop                       (description: 142 chars)
  2.2 Prefilling                             (description: 201 chars)
  2.5 Stop Reasons & Branching               (description: 178 chars)

Existing curriculum (read from dashboard):
  2.1 → description present (142 chars, identical)
  2.2 → description empty
  2.5 → description present (180 chars, DIFFERENT from YAML)

Diff:
  Lecture 2.1 → MATCH (skip — re-run with --force=2.1 to overwrite)
  Lecture 2.2 → CREATE
    + "Why prefilling matters and when to reach for it..."
  Lecture 2.5 → OVERWRITE (requires --force)
    - dashboard: "Walk through stop_reason values and how to branch on each."
    + YAML:      "Stop reasons gate every agentic loop iteration..."

Summary:
  CREATE: 1   MATCH: 1   OVERWRITE (blocked, needs --force): 1
  Net writes if invoked without --force: 1
  Net writes if invoked with --force: 2 (overwrites 2.5)

To apply: re-run without --preview
To overwrite divergent entries: re-run with --force
```

User can then re-invoke without `--preview` to actually deploy.

## Verification

After a run, the user should see:

- Every YAML key with a successful `CREATE` or `OVERWROTE` status now has its
  description visible in the lecture's metadata row.
- Re-running the skill (without `--force`) reports `MATCH` for every key
  that was just deployed (confirms persistence + read-back parity).
- A final screenshot of the curriculum page is saved.

Report success with a table of `Lecture N.M → CREATED | OVERWROTE | MATCHED | SKIPPED | FAILED`
and the final screenshot path.

## Related skills

- `udemy-lecture-description-writer` — produces the YAML this skill consumes
- `udemy-curriculum-populator` — must run BEFORE this skill (creates the
  lecture stubs); shares the same dashboard, same `data-purpose` selectors,
  same auth pattern
- `udemy-coding-exercise-deployer` — sibling deployer, different content
  type, same shape
- `udemy-lecture-writer` — produces the lecture scripts (separate concern
  from the dashboard description blurb)
