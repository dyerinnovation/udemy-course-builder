---
name: udemy-curriculum-populator
description: >
  Populate a Udemy instructor course's `/manage/curriculum/` page with sections
  and lecture stubs by reading the course's planning files (`course-outline.md`
  and `scripts/section-NN-*/section-overview.md`) and driving the Udemy
  dashboard via Playwright MCP or Chrome MCP. Sibling to
  `udemy-landing-populator` — same pattern, different page. Uses Udemy's
  `data-purpose` attributes for stable selectors. Idempotent (skips items that
  already exist by exact title match). Lecture stubs are TITLE-ONLY — no video
  upload, slides, or content body. Never publishes; never deletes; supports a
  `--preview` dry-run mode. Use when a Udemy course is in DRAFT and the
  curriculum is empty (or partially scaffolded) and you need to mirror the
  course's planned section/lecture structure into the dashboard so individual
  content (slides, coding exercises, quizzes) can be deployed afterwards.
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

# Udemy Curriculum Populator

## Overview

Builds out a Udemy course's curriculum (sections + lecture stubs) by reading
the course's planning artifacts and driving the instructor dashboard. This is
the curriculum-page sibling of `udemy-landing-populator` — same auth
pattern, same `data-purpose` selector strategy, same idempotency + safety
rules. Selectors and step sequences live in `playbook.md`.

After this skill runs, the curriculum scaffold matches the course plan — and
sibling deployment skills (`udemy-coding-exercise-deployer`, future
`udemy-quiz-deployer`, etc.) can land their content into the now-existing
sections.

## When to use

- Course is in DRAFT with an empty or partial curriculum, and you have
  `course-outline.md` finalized.
- You need to add a NEW section + its lecture stubs to a course that already
  has some sections.
- You need to verify the dashboard matches `course-outline.md` (idempotent
  re-run reports drift but doesn't change anything unless `--apply`).

## When NOT to use

- **Uploading lecture VIDEO** — out of scope (manual). Lecture stubs are
  title-only.
- **Filling article body, slide attachments, or content type** — handled
  per-lecture-type by future skills (lecture-content-uploader, etc.).
- **Creating coding exercises** — use `udemy-coding-exercise-deployer` after
  this skill has created the parent section.
- **Creating quizzes** — future `udemy-quiz-deployer` (not yet built).
- **Deleting sections or lectures** — never. The skill is additive only.
- **Publishing the course** — never. Always pauses for manual review.

## Required input files

The course repo must contain (produced by `udemy-course-planner`):

| File | Feeds |
|---|---|
| `course-outline.md` | Section titles, lecture title sequences, section ordering |
| `scripts/section-NN-<slug>/section-overview.md` (per section, optional) | Per-section learning objective text used as the section description in Udemy |

The skill refuses to run if `course-outline.md` is missing. Per-section
overview files are optional — if absent, the section is created with an empty
description (which the user can fill in later in the dashboard).

## Invocation

The skill needs:

1. **Course ID** — numeric, from the instructor URL. E.g. `7140821` for
   `https://www.udemy.com/instructor/course/7140821/`.
2. **Course repo path** — absolute path to the repo containing
   `course-outline.md`. Default:
   `/Users/jonathandyer/Documents/dev/udemy-courses/<course-slug>`.

Optional flags:

- `--preview` / `dryRun: true` — produce the full action plan as text WITHOUT
  opening the browser. User reviews, then re-invokes without the flag.
- `--sections=2,3,5` — only process the listed section numbers (skip the
  rest). Default: all sections in `course-outline.md`.
- `--lectures-only` — skip section creation entirely; only add lecture stubs
  inside already-existing sections.
- `--sections-only` — create sections only; skip lecture stubs.
- `--apply` — used during a re-run that previously detected drift; required
  to actually make changes (default behaviour on re-run is report-only).

## Authentication

Same two-backend pattern as `udemy-coding-exercise-deployer` — pick one before
invoking.

### Option A — Chrome MCP (attaches to YOUR Chrome)

1. Open Chrome (your daily browser, signed in to Udemy as the instructor
   account, e.g. `innovation@dyercapital.com`).
2. Keep at least one `udemy.com` tab open.
3. Make sure the Claude-in-Chrome extension is connected
   (`mcp__claude-in-chrome__list_connected_browsers` returns the right
   browser).
4. Invoke the skill. Every click happens in the browser you can see.

Caveat: while the skill is driving Chrome, don't interact with the same
window — competing input causes selector misses.

### Option B — Playwright with persisted profile

1. **First-time setup:**
   ```bash
   npx playwright open --save-storage=~/.config/udemy-deployer/auth.json https://www.udemy.com/join/login-popup/
   ```
   Log in, close the window. Auth state persists.
2. **Subsequent runs:** Playwright loads `auth.json` and arrives at the
   curriculum URL already logged in.
3. **When cookie expires** (Udemy rotates ~every 30 days): the skill aborts
   on the login redirect; re-run the step-1 command.

The skill never prompts for or types credentials. If neither backend has an
authenticated session, ABORT with a pointer to the matching setup option.

## Execution flow

Follow `playbook.md` for every selector and JS snippet. High-level sequence:

1. **Preflight (no browser)**
   - Verify `course-outline.md` exists in the course repo.
   - Parse it: extract every `## Section N: <title>` heading + the indented
     `### Lectures` numbered list under each. Result: `sections[]` where each
     entry has `{number, title, objective?, lectures: [{number, title}]}`.
   - For each section, also try to read
     `scripts/section-NN-<slug>/section-overview.md` and extract the
     "Learning Objectives" bullet list as the `objective`.
   - Report the parsed plan back to the user as a tree:
     ```
     PLAN — would create:
       Section 2: Claude API Fundamentals Bootcamp
         + Lecture 2.1 The Agentic Loop
         + Lecture 2.2 Prefilling
         ...
       Section 3: ...
     ```
   - **Pause for go-ahead before touching the browser.**

2. **Auth**
   - Chrome MCP path: `list_connected_browsers` → expect the
     pre-authenticated browser (e.g. `dyer-innovation-browser`). If multiple
     candidates, ASK the user to pick.
   - Playwright path: load `~/.config/udemy-deployer/auth.json` into a fresh
     context. If file missing, ABORT with the Option B setup command.

3. **Navigate + verify login**
   - URL: `https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/`
   - Wait for `[data-purpose="curriculum-list"]` to be present.
   - If page redirected to `/join/login-popup/`, ABORT (auth setup pointer).

4. **Read existing curriculum** — enumerate every
   `[data-purpose="section-editor"]`, capture title + the lecture rows nested
   inside. This is the IDEMPOTENCY baseline.

5. **Reconcile plan vs. reality**
   - For each planned section: if a section with the same `Section N: <title>`
     already exists, mark as `EXISTS`. Otherwise mark as `CREATE`.
   - For each planned lecture: if its parent section exists AND the lecture
     title already exists in that section, mark `EXISTS`. Otherwise mark
     `CREATE`.
   - Print the diff. If the user invoked without `--apply` AND any drift
     exists, STOP — show the diff and tell them to re-run with `--apply`.

6. **Apply (sections first, then lectures)**
   - Per `CREATE` section (in outline order): click the LAST
     `[data-purpose="add-item-inline"]` (positioned below all sections) →
     click `[data-purpose="add-item-inline-last"]` with `innerText="Section"`
     → fill section title + learning objective → submit. Wait for the new
     `[data-purpose="section-editor"]` to appear.
   - Per `CREATE` lecture (in outline order, within its parent section):
     click the `[data-purpose="add-item-inline"]` immediately after that
     section's last item → click `[data-purpose="add-item-inline-last"]` with
     `innerText="Curriculum item"` → click `[data-purpose="add-lecture-btn"]`
     → fill lecture title → submit.

7. **Verify + report**
   - Re-enumerate the curriculum.
   - Confirm every planned section + lecture is now present.
   - Print a per-section table: `Section N — created/existed/missing`.
   - Take a final screenshot.

## Guardrails

- **Idempotent.** Default behaviour on re-run is report-only — drift is
  shown, no changes made until `--apply` is passed.
- **Additive only.** Never deletes sections or lectures. Never reorders. If
  the user wants something removed, they do it manually in the dashboard.
- **Title match is exact.** Whitespace + casing matter. If
  `course-outline.md` says "Section 2: Claude API Fundamentals Bootcamp" and
  the dashboard says "Section 2: Claude Api Fundamentals Bootcamp", the
  skill treats them as different — surfaces the diff but doesn't auto-fix.
- **Watchdog.** If Udemy returns a validation error (red banner,
  `[role="alert"]`), STOP, screenshot, report. No blind retries.
- **Selector-drift abort.** If any expected `data-purpose` selector returns
  zero matches, STOP, screenshot, log step + selector + URL. Don't try
  alternatives silently.
- **Never click Publish.** Never click Submit for Review. Never click any
  delete button.
- **Never enter credentials.**
- **Pause-and-confirm at section count thresholds.** If the plan would
  CREATE more than 5 sections in one run, pause after the first 2 and ask
  the user to verify before proceeding — sanity check against runaway
  parsing errors.

## Out of scope (v1)

- Lecture VIDEO upload (manual; needs separate skill if automated).
- Lecture article body / description / resources / lab — content type pickers
  (`[data-purpose="lecture-add-content-btn"]`) are NOT touched here; lectures
  are created as bare title-only stubs.
- Reordering or renaming existing sections/lectures.
- Quiz creation in the dashboard (use `udemy-quiz-creator` for the markdown,
  then a future `udemy-quiz-deployer`).
- Coding exercise creation (use `udemy-coding-exercise-deployer` after the
  parent section exists).
- Practice tests / assignments.
- Submitting for review.

## Verification

After a run, the user should see:

- ✅ Every planned section appears as a `[data-purpose="section-editor"]` row
  with the correct title.
- ✅ Every planned lecture appears as a child item of its parent section
  with the correct title.
- ✅ Re-running the skill (without `--apply`) reports zero drift.
- ✅ The Curriculum sidebar in the instructor nav still shows the in-progress
  state (no green checkmark unless other criteria are met — those aren't
  this skill's responsibility).

Report success with a table of `Section N → CREATED | EXISTED | FAILED` and a
final screenshot path.

## Related skills

- `udemy-course-planner` — produces the input files this skill consumes
- `udemy-landing-populator` — sibling deployer for landing/goals/messages
- `udemy-coding-exercise-deployer` — runs AFTER this skill, deploys exercises
  into the now-existing sections
- `udemy-lecture-writer` — produces the lecture scripts (separate from
  pushing the stub into the dashboard)
