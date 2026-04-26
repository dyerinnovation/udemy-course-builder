---
name: udemy-quiz-deployer
description: >
  Deploy a Udemy section quiz from a per-section markdown file in `quizzes/`
  into the dashboard via Chrome MCP. Walks the
  `[data-purpose='add-item-inline']` → 'Curriculum item' →
  `[data-purpose='add-quiz-btn']` flow, then fills the quiz creation form
  (title + each question + answer choices + correct-answer marker + optional
  explanation). Idempotent (skips if a quiz with the same title already exists
  in the target section unless `--force`). Never publishes; supports
  `--preview` dry-run mode. Sibling to `udemy-quiz-creator` (which only
  authors the markdown — it doesn't deploy). Trigger on: 'deploy this quiz',
  'push quiz to Udemy', 'upload section N quiz', 'populate quizzes from
  quizzes/'.
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

# Udemy Quiz Deployer

## Overview

Deploys a per-section knowledge-check quiz from the course repo's `quizzes/`
directory into the Udemy instructor dashboard. The sibling skill
`udemy-quiz-creator` produces the markdown; this skill delivers it through
the `[data-purpose="add-quiz-btn"]` flow on `/manage/curriculum/`.

After this skill runs, each `quizzes/section-NN-*.md` file is mirrored as a
draft Udemy quiz inside the matching section. The quiz is saved unpublished
— the user reviews and publishes manually.

## When to use

- A `quizzes/section-NN-*.md` file is finalized and the parent section
  already exists in the Udemy dashboard (i.e. `udemy-curriculum-populator`
  already ran).
- The user says "deploy this quiz", "push the section 2 quiz", "upload all
  quizzes", "populate quizzes from quizzes/".
- You need to verify the dashboard's quizzes match the local markdown
  (idempotent re-run reports drift but doesn't change anything).

## When NOT to use

- **Authoring a new quiz** → use `udemy-quiz-creator` (markdown only).
- **Publishing the course / quiz** — never. Always pause for manual review.
- **Practice tests** — different `[data-purpose="add-practice-test-btn"]`
  flow; out of scope for v1.
- **Editing an existing quiz's questions** — v1 skips when a same-title quiz
  already exists. Use `--force` to overwrite (re-creates from scratch — does
  NOT diff-merge).
- **Deleting any quiz / question** — never. Strictly additive.
- **Creating the parent section** — must exist. Run
  `udemy-curriculum-populator` first.

## Prerequisites

1. **Target section exists in the dashboard.** The skill will not create
   sections — `udemy-curriculum-populator` must have already mirrored the
   plan.
2. **Quiz markdown file exists** at `quizzes/section-NN-<slug>.md` in the
   course repo.
3. **Authenticated Chrome MCP (or Playwright) session.** See **Browser &
   authentication setup** below — same two-backend pattern as
   `udemy-curriculum-populator` and `udemy-coding-exercise-deployer`. The
   skill never enters credentials.
4. **Udemy numeric course id.** From the instructor URL, e.g. `7140821` for
   `https://www.udemy.com/instructor/course/7140821/manage/curriculum/`.

## Browser & authentication setup (READ BEFORE FIRST RUN)

Identical to `udemy-curriculum-populator`. Pick one backend up front.

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
3. **When the cookie expires** (~30-day rotation): the skill aborts on the
   login redirect; re-run the step-1 command.

If neither backend has a usable session, ABORT with a pointer to the
matching setup option. Never prompt for credentials.

## Quiz markdown format expected (the contract)

Two formats are accepted. The PRIMARY format (used by every quiz file in
the Claude Architect course) is the rich `## Q<N>` form:

```markdown
# Quiz: <Section Title>

**Scope**: <one-sentence what this quiz covers>
**Format**: <count + types, e.g. "10 questions — ~6 MC, ~2 T/F, ~2 multi">

## Q1 (multiple choice) — <tag/scenario reference>

**Stem:**
<question text, possibly multi-line, possibly multi-paragraph>

A) <option text>
B) <option text>
C) <option text>
D) <option text>

**Correct Answer:** B

### Explanation
<explanation text, possibly multi-paragraph>

---

## Q2 (true/false) — <tag>

**Stem:**
**True or False:** <statement>

A) True
B) False

**Correct Answer:** B (False)

### Explanation
<explanation>

---

## Q3 (multi-select) — <tag>

**Stem:**
<stem with "Choose two." hint>

A) <option>
B) <option>
C) <option>
D) <option>

**Correct Answers:** A, B

### Explanation
<explanation>
```

The ALTERNATE format (simpler, GitHub-checkbox style) is also accepted:

```markdown
# Quiz: <Section Title>

> Section: <NN>
> Type: knowledge_check
> Pass threshold: 70%

## Question 1
<question text>

- [ ] Wrong answer
- [x] Correct answer       # `[x]` marks correct
- [ ] Wrong answer
- [ ] Wrong answer

**Explanation:** <optional explanation>

## Question 2
... (same pattern)
```

### Parsing rules (apply to either format)

- **Question type detection:**
  - PRIMARY format: read the `(multiple choice|true/false|multi-select)`
    parenthetical in the `## Q<N>` heading.
  - ALTERNATE format: count `[x]` markers — exactly one `[x]` =
    multiple_choice; multiple `[x]` = multi_select; exactly two options
    labeled "True" / "False" with one `[x]` = true_false.
- **Title:** the H1 line (`# Quiz: <Section Title>`) becomes the Udemy
  quiz title verbatim (including the `Quiz: ` prefix unless overridden by
  `--title-strip-prefix`).
- **Section mapping:**
  - PRIMARY format: parse the section number from the filename slug
    (`section-02-api-bootcamp.md` → Section 2).
  - ALTERNATE format: prefer the `> Section: <NN>` blockquote line if
    present; fall back to filename slug parsing.
- **Explanation:** optional. PRIMARY uses `### Explanation` block (concat
  all paragraphs until the next `---` or `## Q`). ALTERNATE uses the
  `**Explanation:**` inline form.
- **Correct-answer extraction:**
  - PRIMARY: `**Correct Answer:** <letter>` (single) or `**Correct
    Answers:** <letter>, <letter>` (multi). Map letters back to options by
    list order (A=1, B=2, …).
  - ALTERNATE: `[x]` marker on the option line itself.

If the file fails to parse (no recognizable question heading, mismatched
`Correct Answer` letter, zero correct answers on a question), **ABORT**
with a clear "expected format" message that quotes the failing line +
its line number.

## Invocation

The skill needs:

1. **Course id** — numeric, from the instructor URL.
2. **Course repo path** — absolute path to the repo containing `quizzes/`.
   Default: `/Users/jonathandyer/Documents/dev/udemy-courses/<course-slug>`.

Optional flags:

- `--quiz=quizzes/section-NN-<slug>.md` — process a single quiz file.
- `--all` — process every `quizzes/section-NN-*.md` file (skip files that
  don't match the section-NN naming pattern).
- `--preview` / `dryRun: true` — produce the action plan as text WITHOUT
  opening the browser. User reviews, then re-invokes without the flag.
- `--force` — skip the duplicate-title guard (overwrite any existing quiz
  with the same title in the target section by re-creating it).
- `--sections=2,3,5` — only process the listed section numbers (combined
  with `--all`, filters the set).

Exactly one of `--quiz` or `--all` is required.

## Execution flow

Follow `playbook.md` for every selector and JS snippet. High-level
sequence per quiz file:

1. **Preflight (no browser)**
   - Read the quiz markdown file.
   - Parse it per the rules above. Build `{title, section: N, questions:
     [{type, stem, options: [{text, correct}], explanation?}]}`.
   - Refuse to proceed on parse error — surface the failing line.
   - Print the parsed plan (title + question count + per-question type +
     first stem preview).

2. **Auth + navigate**
   - Chrome MCP: `list_connected_browsers` → expect the pre-authenticated
     browser. If multiple candidates, ASK the user to pick.
   - Playwright: load `~/.config/udemy-deployer/auth.json`. If file
     missing, ABORT with the Option B setup command.
   - URL: `https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/`
   - Wait for `[data-purpose="curriculum-list"]`. If redirected to login,
     ABORT (auth pointer).

3. **Locate target section**
   - Use the FLAT-DOM enumeration (see playbook). Find the wrapper whose
     `[data-purpose="section-editor"]` has `item-object-index` matching
     `Section <N>:`. ABORT if not found — section must exist before this
     skill runs.

4. **Idempotency check**
   - Within the wrappers belonging to that section (between this section
     wrapper and the next section wrapper), enumerate every
     `[data-purpose="lecture-editor"]` (Udemy treats quizzes as a
     curriculum-item subtype, so they appear with the same wrapper class —
     differentiate via `item-object-index` text, which reads
     `Quiz <N>:` for quizzes).
   - If a quiz with the same title is present:
     - default → SKIP (report `EXISTS`)
     - with `--force` → DELETE prompt is NOT auto-clicked (skill never
       deletes); instead ABORT with: "Quiz exists; --force does not
       auto-delete. Manually delete the quiz in the dashboard, then re-run."

5. **Add the quiz row**
   - Click `[data-purpose="add-item-inline"]` immediately AFTER the
     section's last item.
   - Wait ~400ms. Click `[data-purpose="add-item-inline-last"]` filtered
     by `innerText === "Curriculum item"`.
   - Wait for the 5-button sub-picker. Click
     `[data-purpose="add-quiz-btn"]` (aria-label `"Add Quiz"`).

6. **Fill the quiz title form**
   - The inline quiz title form appears in place of the new row.
   - Selector for the title input is **TBD** (likely
     `[data-purpose="quiz-title"]` based on Udemy's naming pattern — verify
     on first `--apply` run).
   - Type the quiz title using the React-aware `value` setter (see
     `udemy-curriculum-populator/playbook.md` "Edit-form quirks" section).
   - Click the primary submit (TBD — likely
     `[data-purpose="submit-quiz-form"]` with label `"Add Quiz"`).

7. **Open the quiz editor**
   - May auto-open after submit. If not, click the new quiz row's edit
     affordance (TBD selector).

8. **Per question — add and fill**
   For each parsed question (in order):
   1. Click "Add question" (TBD selector). The question editor surfaces
      a question-type picker.
   2. Select the question type:
      - `multiple_choice` (default)
      - `true_false` if exactly two options labeled "True" / "False" with
        one correct
      - `multi_select` if more than one correct option
   3. Fill the question stem in the question text input (TBD; likely a
      Quill or contenteditable rich-text field — use the React value-setter
      pattern; if it's contenteditable, use `document.execCommand('insertText', false, value)` after focus).
   4. For each answer option (in order):
      - Fill the option text input (TBD).
      - If marked correct, click the correct-answer toggle (TBD).
      - For `multi_select`, multiple options can be marked.
   5. If `explanation` present: fill the explanation field (TBD —
      typically a smaller rich-text input below the answer list).

9. **Save the quiz**
   - Click the save button (TBD — likely
     `[data-purpose="submit-quiz-form"]` or a per-quiz "Save" button at
     the bottom of the editor).
   - Wait for a success indicator (TBD — toast / state change /
     editor closes).

10. **Verify**
    - Re-run the FLAT-DOM enumeration of the target section.
    - Confirm a row matching `Quiz <M>: <title>` is present.
    - Take a screenshot. Print a per-quiz row: `Section N → CREATED |
      EXISTED | FAILED`.

## Safety rules

- **NEVER click Publish.** Save only.
- **NEVER click any delete button.** Even with `--force`, the skill aborts
  rather than auto-deleting an existing quiz.
- **NEVER enter credentials.** If login is required, abort.
- **NEVER create a new curriculum section.** Section must exist.
- **NEVER make in-browser tweaks not in the source markdown.** If the
  user wants a change, they edit the markdown + re-run.
- **NEVER continue past a parse error.** Quote the failing line + line
  number. No silent fallbacks.
- **Selector-drift abort.** If any expected `data-purpose` selector returns
  zero matches, STOP, screenshot, log step + selector + URL. No silent
  alternatives.
- **Idempotent.** Default behaviour on re-run is skip-existing — drift is
  reported, no changes made unless `--force`.
- **Pause-and-confirm at >5 quizzes per run.** If `--all` would deploy
  more than 5 quizzes in a single invocation, pause after the first 2 and
  ask the user to verify before proceeding (sanity check against runaway
  parsing or selector drift).

## Out of scope (v1)

- Practice tests (different `[data-purpose="add-practice-test-btn"]` flow).
- Question reordering, time limits, attempt restrictions, randomization,
  per-question scoring weights.
- Image-based question content (image upload in stem or options).
- Auto-grading rubrics for free-text answers.
- Editing/diffing an existing quiz's questions in place. v1 only creates
  fresh quizzes; updates require manual delete-then-redeploy.
- Quiz preview / "take this quiz as a student" verification.
- Submitting for review.

## Dry-run / preview mode

When invoked with `--preview` or `dryRun: true`, produce the full action
plan as text WITHOUT opening the browser:

```
DRY RUN — udemy-quiz-deployer
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course

Quiz files to deploy:
  quizzes/section-02-api-bootcamp.md → Section 2: Claude API Fundamentals Bootcamp
    Title: "Quiz: Section 2 — Claude API Fundamentals Bootcamp"
    Questions: 10 (7 multiple_choice, 2 true_false, 1 multi_select)
    Q1 preview: "A junior engineer on your team put the airline customer-..."

Pre-flight:
  [parse] OK — 10 questions parsed cleanly from section-02-api-bootcamp.md
  [auth]  Will attach to Chrome MCP browser "dyer-innovation-browser"

Dashboard flow (per quiz):
  [1] Locate Section 2 wrapper in [data-purpose="curriculum-list"]
  [2] Idempotency: enumerate items; check for existing
      "Quiz: Section 2 — Claude API Fundamentals Bootcamp"
  [3] Click last [data-purpose="add-item-inline"] in Section 2
  [4] Click [data-purpose="add-item-inline-last"][innerText="Curriculum item"]
  [5] Click [data-purpose="add-quiz-btn"] (aria-label "Add Quiz")
  [6] Fill quiz-title input (TBD selector); submit (TBD)
  [7] For Q1..Q10: click Add question → set type → fill stem →
      fill 4 options → mark correct → fill explanation
  [8] Click Save (TBD). Verify quiz row appears.

Total to deploy: 1 quiz, 10 questions
To apply: re-run without --preview
```

User reviews, then re-invokes without `--preview` to actually deploy.

## Verification

After a run, the user should see:

- Every targeted quiz appears as a row inside its section, indexed
  `Quiz <M>:` with the markdown's title.
- Re-running the skill (same args, no `--force`) reports `EXISTED` for
  every previously-deployed quiz — zero changes.
- The Curriculum sidebar in the instructor nav still shows
  in-progress (no green-published indicator triggered by this skill).

Report success with a per-quiz table:
`Section N — CREATED | EXISTED | FAILED — <questions added>`
and a final screenshot path.

## Related skills

- `udemy-quiz-creator` — sibling that produces the markdown this skill
  consumes (markdown-only — does NOT deploy).
- `udemy-curriculum-populator` — must run BEFORE this skill so the parent
  sections exist.
- `udemy-coding-exercise-deployer` — closest sibling pattern (same
  `add-item-inline` → `Curriculum item` → picker-button flow, but lands
  exercises instead of quizzes).
- `udemy-landing-populator` — sibling deployer for landing/goals/messages.
