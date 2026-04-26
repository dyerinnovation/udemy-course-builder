---
name: udemy-coding-exercise-deployer
description: "Deploy a pre-authored Udemy coding exercise from the repo into the Udemy instructor dashboard via browser automation (Playwright or Chrome MCP). Takes a path to an exercise directory (5 files: exercise.md + learner.py + solution.py + evaluation.py + explanation.md), drives the dashboard through the 13-step coding-exercise creation flow, runs Udemy's built-in test pass, and saves the exercise unpublished for user review. Trigger on: 'deploy this coding exercise', 'push exercise X to Udemy', 'upload the exercise at [path]', 'populate the Udemy console with [exercise id]'. Supports a --preview dry-run mode. Never publishes — user controls the publish step. Never enters credentials — requires user's Chrome profile to already be logged in."
---

# Udemy Coding Exercise — Deployer

You deploy a pre-authored coding exercise from the course repo's `labs/coding-exercises/` tree into the Udemy instructor dashboard. The sibling skill `udemy-coding-exercise-authoring` produces the exercise; this skill delivers it.

## When to use

- The user points you at an exercise directory and asks you to deploy it.
- The user says "push this to Udemy", "upload the exercise", "populate the dashboard", etc.

## When NOT to use

- **Authoring a new exercise** → use `udemy-coding-exercise-authoring`.
- **Publishing** (the final go-live step) — never do this. Stop at Save. User reviews then publishes manually.
- **Editing credentials / logging in** — never do this. Abort if the user isn't already logged in.
- **Creating a new curriculum section** — the target section must already exist. Use the `udemy-landing-populator` pattern if you need section-level dashboard work.

## Prerequisites

1. **5-file exercise directory** exists at a known path (e.g. `labs/coding-exercises/section-2/01-parse-stop-reason/`).
2. **Udemy course slug** — URL or ID of the target course (e.g. `https://www.udemy.com/course/claude-certified-architect-foundations/manage/curriculum/`).
3. **A browser session already authenticated to Udemy** — see the **Browser & authentication setup** section immediately below. The skill never enters credentials.
4. **Dogfood test has passed locally** — run it as a pre-flight check before touching the browser.

## Browser & authentication setup (READ BEFORE FIRST RUN)

The skill drives a real browser at `udemy.com/instructor/...`. It cannot log in for you — Udemy's anti-bot protections plus the no-credentials safety rule make that explicit. **You must establish an authenticated session before invoking this skill.** There are two supported backends; pick one up front:

### Option A — Chrome MCP (attaches to YOUR Chrome)

This is the recommended path when you're at your own machine.

1. Open Chrome (your daily browser, with your Udemy login cookie).
2. Sign in to Udemy as the instructor account (e.g. `innovation@dyercapital.com`).
3. Open at least one tab on `udemy.com` — keeps the session warm.
4. Make sure the Claude-in-Chrome extension is connected (skill checks `mcp__claude-in-chrome__list_connected_browsers`). If not connected, the skill aborts with install instructions rather than silently failing.
5. Invoke the skill. It will use **your already-authenticated Chrome session** — every click happens in the browser you can see.

Caveat: while the skill is driving Chrome, avoid using the same window manually — competing input causes selector misses. Open a different window/profile if you need to multitask.

### Option B — Playwright with a persisted profile

Use this when running headless, on a server, or you don't want the skill touching your daily Chrome.

1. **First-time setup (one manual login):**
   ```bash
   npx playwright open --save-storage=~/.config/udemy-deployer/auth.json https://www.udemy.com/join/login-popup/
   ```
   Log in to Udemy in the window that opens. Close the window when the dashboard loads. The auth state (cookies + localStorage) is now persisted to `~/.config/udemy-deployer/auth.json`.
2. **Every subsequent run:** the skill loads that storage state into a fresh Playwright context, so the deployer arrives at `manage/curriculum/` already logged in.
3. **When the cookie expires** (Udemy rotates sessions ~every 30 days), step 0c will redirect to login → skill aborts → re-run the step-1 command.

### What the skill does NOT do

- It does **not** prompt for or type credentials anywhere.
- It does **not** open a new browser if neither backend is set up — it aborts with the message "No authenticated Udemy session found. Run Option A or Option B setup, then retry."
- It does **not** save credentials to the repo or to the skill directory.

### Step 0c re-states the check

Before clicking anything, the skill navigates to `https://www.udemy.com/course/<slug>/manage/curriculum/`. If that URL redirects to a login page, the skill aborts with the appropriate setup pointer (Option A or B based on the active backend). This is a hard gate — there's no "try anyway" path.

## Input format

Expected from the user:
- **Path to exercise directory** (absolute or repo-relative).
- **Udemy course URL** (full URL to the `.../manage/curriculum/` page).

Optional flags:
- `--preview` or `dryRun: true` — produce the full action plan as text WITHOUT clicking anything. User reviews, then re-invokes without the flag.
- `--force` — skip the duplicate-title guard (overwrite any existing exercise with the same title in the target section).

## The 13-step dashboard flow

### Pre-flight (before touching the browser)

0a. **Read the 5 exercise files.** Parse `exercise.md` YAML frontmatter (title, section, language, hints, estimated_minutes). Load `solution.py`, `evaluation.py`, `learner.py`, `explanation.md` as strings.

0b. **Dogfood-test.** Run:
```bash
cd <exercise-dir>
cp learner.py learner.py.bak
cp solution.py learner.py
python -m unittest evaluation.py
mv learner.py.bak learner.py
```
If tests don't all pass, ABORT with a clear error. Never deploy a broken exercise.

0c. **Verify login.** Navigate to the course's Curriculum URL. If redirected to login, ABORT and point the user at Option A or B in the **Browser & authentication setup** section above (whichever backend is active). Never enter credentials. Otherwise proceed.

### Live dashboard flow (13 steps)

| # | Action | Selector / Target | Expected state after |
|---|---|---|---|
| 1 | Navigate to Curriculum page | `https://www.udemy.com/course/<slug>/manage/curriculum/` | Page loads, sections visible |
| 2 | Find target section row | Match by text: "Section N: <title>" from frontmatter | Section row DOM node identified |
| 3 | **Duplicate-title guard:** search within the section for an existing item matching `title:` from frontmatter. If found and `--force` not set, prompt user. | | No duplicate OR user confirmed overwrite |
| 4 | Hover grey space inside target section to reveal `+` icon, click it | `+` button in section | `+` menu opens |
| 5 | Click "Coding Exercise" in the popup menu | menu item labeled "Coding Exercise" | Title dialog appears |
| 6 | Type the exercise title | title input field | Input populated |
| 7 | Click "Add Coding Exercise" | primary submit button | Exercise added to curriculum, pencil icon appears |
| 8 | Click the pencil icon on the new exercise | pencil/edit affordance on the exercise row | Editor opens |
| 9 | Select Python as the language | language dropdown → "Python" | Language set; solution/evaluation file tabs visible |
| 10 | Paste solution code: click Solution file tab, clear, paste `solution.py` content | monaco editor in Solution tab | Code visible |
| 11 | Paste evaluation code: click Evaluation file tab, clear, paste `evaluation.py` content | monaco editor in Evaluation tab | Code visible |
| 12 | Click "Run tests" → wait for pass. If fail, ABORT + dump stderr. | Run tests button | Green test result |
| 13 | Guide learners tab: paste `learner.py` into Learner file editor, paste `exercise.md` body (strip frontmatter) into "Guide learners" problem area, add each hint via "Add hint" + paste text, paste `explanation.md` into "Instructor solution explanation". Click **Save** (NOT Publish). | multiple editors + buttons | Save confirmation; exercise persisted unpublished |

### Success criteria

- Test-pass indicator appears green after step 12.
- "Saved" toast / state indicator after step 13.
- Exercise appears in the curriculum list in draft state.

## Error handling

### Selector drift (element not found)

Udemy's dashboard is a React app — class names and data-test-ids change. If any step's expected selector fails:

1. Take a screenshot, save to `/tmp/udemy-deploy-drift-<timestamp>.png`.
2. Log the step number, expected selector, and page URL.
3. ABORT. Do not try alternative selectors silently — that leads to wrong-button clicks.
4. Tell the user: "Step N failed to find [selector]. Dashboard UI may have changed. Screenshot at [path]. Please update the skill with the new selector."

### Test failure at step 12

If Udemy's "Run tests" returns a failure:
1. Capture the error text from the test results panel.
2. ABORT the save — don't save a broken exercise.
3. Tell the user: "Udemy's test run failed with: [text]. Either solution.py is wrong for the evaluation.py here, or evaluation.py has a subtle Udemy-sandbox incompatibility. Fix the source files, re-run dogfood test locally, then retry."

### Login check fails

If the course URL redirects to login:
- ABORT.
- Detect which backend is active (Chrome MCP vs Playwright persisted profile) and point the user at the matching setup path:
  - **Chrome MCP:** "Udemy is asking to log in. Open Chrome, sign in to Udemy as the instructor account (e.g. `innovation@dyercapital.com`), keep a `udemy.com` tab open, then re-run the skill. See **Browser & authentication setup → Option A**."
  - **Playwright persisted profile:** "The persisted Udemy session at `~/.config/udemy-deployer/auth.json` has expired or is missing. Re-run the one-time login: `npx playwright open --save-storage=~/.config/udemy-deployer/auth.json https://www.udemy.com/join/login-popup/` then retry. See **Browser & authentication setup → Option B**."
- Never attempt to enter credentials yourself.

### Duplicate title found

If step 3 finds an exercise with the same title already in the section AND `--force` isn't set:
- Show the user the existing exercise's title + location.
- Ask: "An exercise with this title already exists. Overwrite? Skip? Abort?"
- Default to Abort if the user doesn't respond.

### Network flake

If a navigation or click times out once, retry ONCE after 3 seconds. If it fails twice, treat as selector drift and abort.

## Dry-run / preview mode

When invoked with `--preview` or `dryRun: true`, produce the complete action plan as text WITHOUT opening the browser:

```
DRY RUN — would deploy exercise: s2-01-parse-stop-reason
Target: https://www.udemy.com/course/<slug>/manage/curriculum/
Section: Section 2 — Claude API Fundamentals Bootcamp

Pre-flight:
  [0a] Read 5 files from labs/coding-exercises/section-2/01-parse-stop-reason/
  [0b] Run dogfood test (cp solution.py learner.py && python -m unittest evaluation.py)
  [0c] Verify authenticated Udemy session (Chrome MCP attaches to user's
       Chrome OR Playwright loads ~/.config/udemy-deployer/auth.json).
       If redirect to login → ABORT + point at Option A/B setup.

Dashboard flow:
  [1] Navigate: https://www.udemy.com/course/<slug>/manage/curriculum/
  [2] Find section row: "Section 2: Claude API Fundamentals Bootcamp"
  [3] Check for duplicate: "Parse stop_reason and Branch the Loop"
  [4] Click + icon in section
  [5] Click "Coding Exercise" menu item
  [6] Type title: "Parse stop_reason and Branch the Loop"
  [7] Click "Add Coding Exercise"
  [8] Click pencil icon
  [9] Select language: Python
  [10] Paste solution.py (234 chars):
       def next_action(response: dict) -> str:
           """..."""
           if response.get("stop_reason") == "tool_use":
               return "continue"
           return "done"
  [11] Paste evaluation.py (1.8 KB, 8 test cases)
  [12] Click "Run tests" — expect pass
  [13] Paste learner.py (342 chars), problem statement (1.2 KB), 4 hints, explanation.md (1.5 KB). Click Save (NOT Publish).

Exercise will be saved UNPUBLISHED. User reviews + publishes manually.
```

User can then re-invoke without `--preview` to actually deploy.

## Safety rules

- **NEVER click Publish.** Save only. Publish is the user's final review step.
- **NEVER enter credentials.** If login is required, abort.
- **NEVER create a new curriculum section.** Target section must exist. Abort if missing.
- **NEVER make edits in the browser editor that aren't in the source files.** If the user wants a tweak, they edit the source + re-run the skill.
- **NEVER silently overwrite** an existing exercise. Duplicate-title guard must prompt unless `--force`.
- **NEVER continue past a failed test.** Step 12's Run tests must pass. A red result halts the flow.
- **NEVER trust Udemy's auto-save.** Always click the explicit Save button at step 13.

## Cross-references

- **Format spec:** `labs/coding-exercises/README.md` in the course repo
- **Seed exercise:** `labs/coding-exercises/section-2/01-parse-stop-reason/` in the course repo
- **Sibling skill (authoring):** `udemy-coding-exercise-authoring`
- **Sibling skill pattern (similar Playwright dashboard driver):** `udemy-landing-populator`
- **Udemy docs (instructor creation flow):** https://support.udemy.com/hc/en-us/articles/115002883587-How-to-Create-a-Coding-Exercise
- **Udemy docs (student experience):** https://support.udemy.com/hc/en-us/articles/229606768-Learning-With-Coding-Exercises
