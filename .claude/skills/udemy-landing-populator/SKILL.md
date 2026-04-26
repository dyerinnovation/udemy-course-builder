---
name: udemy-landing-populator
description: >
  Populate a Udemy instructor course's landing-page, intended-learners, and
  course-messages fields from markdown source files using the Playwright MCP.
  Reads from `course-metadata/` in the course repo and fills Udemy's form
  inputs by `data-purpose` attributes and proximity-to-heading selectors. Use
  when a Udemy course is in DRAFT and you need to apply pre-written copy to
  the Intended Learners, Course Landing Page, and Course Messages pages. Does
  NOT click "Submit for Review" — always pauses for human confirmation.
allowed-tools: >
  mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot,
  mcp__playwright__browser_click, mcp__playwright__browser_type,
  mcp__playwright__browser_fill_form, mcp__playwright__browser_select_option,
  mcp__playwright__browser_press_key, mcp__playwright__browser_evaluate,
  mcp__playwright__browser_wait_for, mcp__playwright__browser_take_screenshot,
  mcp__playwright__browser_tabs, Read, Bash
---

# Udemy Landing Page Populator

## Overview

Fills out a Udemy instructor course's three initial-info sections —
**Intended Learners**, **Course Landing Page**, and **Course Messages** —
by reading structured markdown files from the course repo's
`course-metadata/` directory and driving the Udemy instructor UI with the
Playwright MCP. Selector map and fill procedure live in `playbook.md`.

## Required input files

The course repo must contain a `course-metadata/` directory with:

| File | Feeds |
|---|---|
| `landing-page.md` | `/manage/basics` — title, subtitle, description, level, category, subcategory, primary topic |
| `intended-learners.md` | `/manage/goals` — learning objectives, prerequisites, audience personas |
| `course-messages.md` | `/manage/communications/messages` — welcome + congratulations |
| `instructor-bio.md` | Instructor profile (separate `/profile/*` page — handled via note, not automated in v1) |

These are produced by the drafting workflow — the skill refuses to run if
any of the three primary files are missing.

## Invocation

The skill needs two inputs from the user:

1. **Course ID** — numeric, from the instructor URL. E.g. `7140821` for
   `https://www.udemy.com/instructor/course/7140821/`.
2. **Course repo path** — absolute path to the repo containing
   `course-metadata/`. Default:
   `/Users/jonathandyer/Documents/dev/udemy-courses/<course-slug>`.

Ask for both if not provided.

## Authentication

Udemy's instructor pages require an authenticated session. The Playwright
MCP opens its own browser instance, so the Udemy cookie jar is NOT shared
with the user's main Chrome. Two supported modes:

**Mode A — Fresh browser, user logs in once (default).**
1. Skill opens `https://www.udemy.com/join/login-popup/` via Playwright.
2. Skill pauses with a clear message: "Please log into Udemy in the
   Playwright-managed browser window. Type 'ready' when you're signed in."
3. After the user confirms, session persists for the remainder of the run.

**Mode B — CDP connect.** If the user explicitly launched Chrome with
`--remote-debugging-port=9222`, Playwright can attach to it and inherit the
existing Udemy login. Only use this if the user requests it.

## Execution flow

Follow `playbook.md` section-by-section. High-level sequence:

1. **Preflight**
   - Verify all required markdown files exist (`Bash: ls course-metadata/`).
   - Parse each file into structured fields (see `playbook.md` § Parsing).
   - Report the parsed summary back to the user — ask for go-ahead before
     touching the browser.

2. **Auth**
   - Navigate to the instructor course root:
     `https://www.udemy.com/instructor/course/<ID>/`.
   - If redirected to login, prompt user (Mode A above).

3. **Fill Intended Learners** — `/manage/goals`
4. **Fill Course Landing Page** — `/manage/basics`
5. **Fill Course Messages** — `/manage/communications/messages`

After each section: click the page's `Save` button, wait for the sidebar
checkmark to flip to green (use `browser_wait_for` on the checkmark
selector per `playbook.md`), and take a screenshot for the user.

6. **Hand off to human**
   - Remind the user that the course image, promo video, and instructor
     profile still require manual upload / update. Reference the spec files
     (`course-image-spec.md`, `promo-video-script.md`, `instructor-bio.md`).
   - **NEVER click "Submit for Review"** — that's a human decision.

## Guardrails

- **Idempotent**: fields that already hold the target value should not be
  re-typed (use `browser_evaluate` to read current value first).
- **No destructive actions**: never delete existing objectives/messages —
  if a field already has content the skill does not overwrite. Surface the
  conflict to the user and ask.
- **Pause before Save on pricing**: pricing is out of scope for v1. If
  asked to fill pricing, refuse and ask the user to set it manually.
- **Watchdog**: if Udemy returns a validation error (red banner, `role=alert`),
  stop, screenshot, and report. Do not retry blindly.

## Out of scope (v1)

- Instructor bio / profile photo upload (lives on a different subdomain,
  separate auth flow)
- Course image and promo video uploads (require asset files not tracked in
  `course-metadata/`; the skill prints upload-ready paths but does not upload)
- Pricing
- Curriculum / lectures / quizzes (handled by `udemy-course-planner` +
  `udemy-lecture-writer` + `udemy-quiz-creator`)
- Submitting for review

## Verification

After a run, the user should see:
- ✅ Sidebar green checkmark next to Intended learners, Course landing page,
  and Course messages.
- Course card preview shows the new title + subtitle.
- Reloading the form shows the filled values persisted (no silent reverts).

Report success with a per-section checkbox list and any skipped/out-of-scope
items that still need manual work.
