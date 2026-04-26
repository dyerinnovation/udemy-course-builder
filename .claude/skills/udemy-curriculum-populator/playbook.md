# udemy-curriculum-populator — Playbook

Operating reference for `/manage/curriculum/`. Selectors captured live on
2026-04-26 from `https://www.udemy.com/instructor/course/7140821/manage/curriculum/`.
If Udemy rotates `data-purpose` attributes, the skill must re-capture via a
read pass before any clicks.

## Key insight: Udemy uses `data-purpose`

Same as `udemy-landing-populator`. `data-purpose` attributes are stable
across React re-renders and across UI revs because they're semantic markers
on Udemy's side, not generated class names. **Prefer them over CSS class
matches at every step.**

## URL

```
https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/
```

The instructor URL format uses a numeric course id, NOT the public slug. Read
the id from the URL while viewing the course in the instructor dashboard. The
public `/course/<slug>/` URL is for students and will not work here.

## Confirmed selectors (2026-04-26 recon, expanded 2026-04-26 preview run, edit-form selectors added 2026-04-26 rename run)

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A section row | `[data-purpose="section-editor"]` |
| A lecture row | `[data-purpose="lecture-editor"]` |
| Title text inside a section OR lecture row | `[data-purpose="item-full-title"]` (innerText starts with `"Section N:"` or `"Lecture N:"` — strip prefix to get the bare title) |
| Order/index inside a section OR lecture row | `[data-purpose="item-object-index"]` (innerText is literally `"Section N:"` / `"Lecture N:"`) |
| Section edit button | `[data-purpose="section-edit-btn"]` |
| Section delete button (DO NOT auto-click) | `[data-purpose="section-delete-btn"]` |
| Lecture edit button | `[data-purpose="lecture-edit-btn"]` |
| Lecture delete button (DO NOT auto-click) | `[data-purpose="lecture-delete-btn"]` |
| Lecture collapse toggle | `[data-purpose="lecture-collapse-btn"]` |
| Lecture inline edit area (when expanded) | `[data-purpose="edit-content-wrapper"]` and `[data-purpose="edit-content"]` |
| Inline insert + (between every pair of items, always visible — no hover) | `[data-purpose="add-item-inline"]` |
| Choice that appears after clicking + | `[data-purpose="add-item-inline-last"]` (innerText is `"Curriculum item"` OR `"Section"`) |
| Coding Exercise picker | `[data-purpose="add-coding-exercise-btn"]` (aria-label `"Add Coding Exercise"`) |
| Lecture picker | `[data-purpose="add-lecture-btn"]` (aria-label `"Add Lecture"`) |
| Quiz picker | `[data-purpose="add-quiz-btn"]` |
| Practice Test picker | `[data-purpose="add-practice-test-btn"]` |
| Assignment picker | `[data-purpose="add-assignment-btn"]` |
| Inside a lecture row: pick content type (Video/Article/etc) — NOT used by this skill | `[data-purpose="lecture-add-content-btn"]` |
| Section edit form (inline, opens in place of the row) | `[data-purpose="section-form"]` (FORM); fields wrapped in `[data-purpose="section-form-group-title"]` and `[data-purpose="section-form-group-description"]` |
| Section title input (inside the inline edit form) | `[data-purpose="section-title"]` (INPUT, `type="text"`, `maxLength=80`, placeholder `"Enter a Title"`) |
| Section learning-objective input (inside the inline edit form) | `[data-purpose="section-objective"]` (INPUT, `type="text"`, `maxLength=200`, placeholder `"Enter a Learning Objective"`) |
| Section save button | `[data-purpose="submit-section-form"]` (BUTTON, `type="submit"`, label `"Save Section"`) |
| Section cancel button | `[data-purpose="cancel-section-form"]` (BUTTON, label `"Cancel"`) |
| Lecture title input (inside the inline edit form) | `[data-purpose="lecture-title"]` (INPUT, `type="text"`, `maxLength=80`, placeholder `"Enter a Title"`) |
| Lecture save button | `[data-purpose="submit-lecture-form"]` (BUTTON, `type="submit"`, label `"Save Lecture"`) |
| Lecture cancel button | `[data-purpose="cancel-lecture-form"]` (BUTTON, label `"Cancel"`) |

## DOM model — sections and lectures are SIBLINGS, not nested

This is the most important correction surfaced by the 2026-04-26 preview run. The original (now-corrected) playbook assumed lectures were nested inside `[data-purpose="section-editor"]`. They're not — every curriculum item (section row OR lecture row) is a direct child of `[data-purpose="curriculum-list"]`, each wrapped in a `div.js-curriculum-item-draggable.curriculum-list--list-item--xn0`.

To find lectures belonging to Section N:
1. Walk `curriculumList.children` in order.
2. Find the wrapper containing the matching `[data-purpose="section-editor"]` (use the `item-object-index` text or the title to match).
3. Continue forward — every consecutive wrapper containing `[data-purpose="lecture-editor"]` belongs to that section.
4. Stop at the next wrapper containing a `[data-purpose="section-editor"]`.

Reference enumeration (read-only):
```js
const list = document.querySelector('[data-purpose="curriculum-list"]');
const wrappers = list.querySelectorAll(':scope > div.js-curriculum-item-draggable, :scope > div.curriculum-list--list-item--xn0');
const items = [];
wrappers.forEach(w => {
  const sec = w.querySelector('[data-purpose="section-editor"]');
  const lec = w.querySelector('[data-purpose="lecture-editor"]');
  const titleEl = w.querySelector('[data-purpose="item-full-title"]');
  if (sec)        items.push({kind: 'section', title: titleEl?.innerText.replace(/^Section\s+\d+:\s*/, '').trim()});
  else if (lec)   items.push({kind: 'lecture', title: titleEl?.innerText.replace(/^Lecture\s+\d+:\s*/, '').trim()});
});
```

## Menu behaviour notes

- The `+` picker is **inline-expanded** (sticky), NOT a popover. Clicking the
  same `+` button again toggles it closed. Escape and outside-click do NOT
  close it.
- The `+` is always visible — there is no hover-to-reveal behaviour to
  emulate.
- Clicking `+` always shows TWO choices: `Curriculum item` and `Section`.
  Picking `Curriculum item` reveals the 5-button sub-picker (Lecture / Quiz /
  Coding Exercise / Practice Test / Assignment).

## Parsing — `course-outline.md` → planned tree

The outline file uses these markdown conventions:

```
## Section N: <Section title>

[free-text paragraph(s)]

**Estimated Duration**: ~XX minutes

### Lectures
N.1 <Lecture 1 title>
N.2 <Lecture 2 title>
...

### Quiz: <quiz title>
...

### Downloadable Resources
...
```

Extraction rules:

- **Sections.** Every line matching `/^## Section (\d+): (.+)$/`. `number` is
  group 1; `title` is group 2.
- **Lectures (standard sections).** Within a section block (between this
  `##` and the next), every line matching `/^(\d+)\.(\d+)\s+(.+?)$/` under
  the `### Lectures` heading. `number` is `${maj}.${min}`; `title` is the
  rest.
- **Lectures (demo sections).** Sections whose title matches
  `/^Demo \d+ — /` typically have NO `### Lectures` block (the section IS
  one walkthrough). Auto-generate **two** planned lectures for each demo
  section:
  1. `N.1 Exercise` — the hands-on activity students complete
  2. `N.2 Solution Video` — the recorded walkthrough that explains the
     solution
  This applies to Sections 8-11 in the Claude Architect course (Demo 1
  through Demo 4). The split mirrors the standard exercise-then-solution
  structure used across the course.
- **Skip headings:** `### Quiz:`, `### Downloadable Resources`, `### Labs`,
  etc. — these are NOT lectures.
- **Lecture title hygiene:** trim trailing whitespace, strip any trailing
  `(NN min)` time hints.

### Per-section objective (optional)

If the file `scripts/section-NN-<slug>/section-overview.md` exists in the
course repo, extract the Learning Objectives bullet list:

```
## Learning Objectives

By the end of this section, students will be able to:
- <objective 1>
- <objective 2>
...
```

Concatenate the bullets into a single paragraph (separator: `". "`) for use
as the section description in Udemy. If the file is missing, leave the
section description empty (user can fill in later).

## Reading existing curriculum (idempotency baseline)

Use the FLAT-DOM enumeration documented above — section and lecture wrappers
are siblings under `[data-purpose="curriculum-list"]`, not nested. Group
lectures into sections by walking the wrappers in order:

```js
const list = document.querySelector('[data-purpose="curriculum-list"]');
const wrappers = list.querySelectorAll(':scope > div.js-curriculum-item-draggable, :scope > div.curriculum-list--list-item--xn0');
const result = [];
let currentSection = null;
wrappers.forEach(w => {
  const sec = w.querySelector('[data-purpose="section-editor"]');
  const lec = w.querySelector('[data-purpose="lecture-editor"]');
  const idxEl = w.querySelector('[data-purpose="item-object-index"]');
  const titleEl = w.querySelector('[data-purpose="item-full-title"]');
  if (sec) {
    const m = idxEl?.innerText.match(/Section\s+(\d+):/);
    currentSection = {
      number: m ? Number(m[1]) : null,
      title: titleEl?.innerText.replace(/^Section\s+\d+:\s*/, '').trim(),
      lectures: []
    };
    result.push(currentSection);
  } else if (lec && currentSection) {
    const m = idxEl?.innerText.match(/Lecture\s+(\d+):/);
    currentSection.lectures.push({
      number: m ? `${currentSection.number}.${m[1]}` : null,
      title: titleEl?.innerText.replace(/^Lecture\s+\d+:\s*/, '').trim()
    });
  }
});
JSON.stringify(result, null, 2);
```

Note: lecture numbering in the dashboard is per-section (`Lecture 1:`,
`Lecture 2:`, etc. restart at 1 within each section), NOT the dotted `2.5`
form used in `course-outline.md`. The skill must reconcile by mapping
position-within-section: planned `2.5` matches the 5th `lecture-editor`
under Section 2.

## Section creation flow

For each `CREATE` section in the plan:

1. Find the LAST `[data-purpose="add-item-inline"]` on the page — this is the
   "add new section at the end" insertion point:
   ```js
   const adds = document.querySelectorAll('[data-purpose="add-item-inline"]');
   adds[adds.length - 1].click();
   ```
   For inserting a section in the MIDDLE (rare — outline order should match
   creation order), use the `add-item-inline` immediately above the section
   that should come after it.

2. Wait for the picker to render (~400ms), then click the "Section" choice:
   ```js
   const choices = document.querySelectorAll('[data-purpose="add-item-inline-last"]');
   const sectionBtn = Array.from(choices).find(b => b.innerText.trim() === 'Section');
   sectionBtn.click();
   ```

3. The inline section form appears in place of the new row. Inputs
   (confirmed via the rename run — assumed identical for create):
   - `[data-purpose="section-title"]` (max 80, plain title — Udemy renders
     the `Section N:` prefix on its own; do NOT include it in the typed
     value)
   - `[data-purpose="section-objective"]` (max 200, learning objective)

4. Type the title (plain — no `Section N:` prefix; the dashboard adds it).

5. Type the objective (single paragraph from `section-overview.md` — see
   parsing rules above). Truncate to 200 chars if needed.

6. Click `[data-purpose="submit-section-form"]` (label "Save Section").
   Use the React-aware `value` setter described in the "Edit-form quirks"
   section above before clicking.

7. Wait for `[data-purpose="section-form"]` to disappear AND for a new
   `[data-purpose="section-editor"]` matching the title to appear (poll up
   to 5s).

## Lecture creation flow

For each `CREATE` lecture in the plan:

1. Find the parent section by matching `[data-purpose="section-editor"]`
   against the planned section title.

2. Find the `[data-purpose="add-item-inline"]` immediately AFTER the
   section's last existing item (this places the new lecture at the bottom of
   the section). For a brand-new section just created, that's the first +
   that appears below it.

3. Click the +. Wait ~400ms. Click the `add-item-inline-last` button with
   `innerText === "Curriculum item"`.

4. Wait for the 5-button sub-picker. Click `[data-purpose="add-lecture-btn"]`
   (aria-label `"Add Lecture"`).

5. The inline lecture form appears. Input (confirmed via the rename run —
   assumed identical for create): `[data-purpose="lecture-title"]`
   (max 80, plain title — dashboard adds the `Lecture N:` prefix).

6. Type the lecture title using the React-aware `value` setter described
   in the "Edit-form quirks" section. Click
   `[data-purpose="submit-lecture-form"]` (label "Save Lecture").

7. Wait for `[data-purpose="lecture-form"]` (or
   `[data-purpose*="lecture"][data-purpose$="form"]`) to disappear AND for
   the new lecture row to appear at the bottom of the parent section.

## Closing the picker without committing

The picker is sticky. To dismiss it without picking anything, click the
ORIGINAL `+` again (toggles it closed). Do NOT rely on Escape or
outside-click — neither works.

```js
// Reopen the same + that opened the picker → it collapses
document.querySelector('[data-purpose="add-item-inline"]:not([aria-expanded="false"])')?.click();
```

(Note: `aria-expanded` on `add-item-inline` was not verified during recon.
If it doesn't exist, track the originally-clicked `+` button reference in
the skill state and re-click it.)

## TBD — captured during first real `--apply` run

These selectors are still pending real-run capture:

- Validation error banner (`[role="alert"]` is the assumption — verify)
- Section/Lecture **creation** dialog selectors (after clicking the `+` →
  Section / Curriculum item → Add Lecture path). These are likely the SAME
  selectors as the edit form (Udemy reuses the inline form for both create
  and edit), but the create flow has not yet been driven end-to-end. Verify
  on first real `--apply` run.

**RESOLVED** (no longer TBD as of 2026-04-26):

- ~~Lecture row → child of `[data-purpose="section-editor"]`~~ — wrong model. Lecture rows are SIBLINGS, not children. Selector: `[data-purpose="lecture-editor"]`. See "DOM model" section above.
- ~~Section title input / Section learning-objective input / Section submit button~~ — captured during the 2026-04-26 Section 1 rename. See the selector table above (`section-title`, `section-objective`, `submit-section-form`).
- ~~Lecture title input / Lecture submit button~~ — captured during the 2026-04-26 Lecture 1.1 rename. See the selector table above (`lecture-title`, `submit-lecture-form`).

## Edit-form quirks (captured 2026-04-26 rename run)

- The section/lecture edit form is **inline** — clicking
  `[data-purpose="section-edit-btn"]` (or the lecture equivalent) replaces
  the row in-place with a `[data-purpose="section-form"]` (or lecture form).
  No modal/dialog overlay is opened.
- The section form exposes BOTH a title input (`section-title`, max 80
  chars) AND a learning-objective input (`section-objective`, max 200
  chars). The lecture form exposes ONLY a title input (`lecture-title`,
  max 80 chars) — there is no per-lecture description here.
- React-controlled inputs: setting `.value` directly will NOT propagate to
  React's internal state. Use the native `value` setter and dispatch
  `input` + `change` events:
  ```js
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, newValue);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  ```
- After clicking `submit-section-form` / `submit-lecture-form`, the button
  goes `disabled=true` immediately and the form is replaced by the row
  showing the new title within ~1s. Poll `[data-purpose="section-form"]`
  (or lecture-form) absence to detect commit completion.
- Both submit buttons use `type="submit"` — pressing Enter inside the title
  input also submits.

## Worked example — `--preview` output

For a course with `course-outline.md` listing 7 sections, where Section 1
already exists in Udemy with 1 lecture, and the user runs:

```
udemy-curriculum-populator \
  --course-id 7140821 \
  --course-repo ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --preview
```

Expected text output:

```
DRY RUN — udemy-curriculum-populator
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course

Parsed plan from course-outline.md:
  Section 1: Course Introduction & Exam Strategy (1 lecture)
  Section 2: Claude API Fundamentals Bootcamp (14 lectures)
  Section 3: Domain 1 — Agentic Architecture (12 lectures)
  Section 4: Domain 2 — Tool Design & MCP (16 lectures)
  Section 5: Domain 3 — Claude Code (15 lectures)
  Section 6: Domain 4 — Prompt Eng & Structured Output (12 lectures)
  Section 7: Domain 5 — Context Mgmt & Reliability (17 lectures)

Existing curriculum (read from dashboard):
  Section 1: Introduction (1 lecture: "Introduction")

Diff:
  Section 1 — TITLE MISMATCH: plan="Course Introduction & Exam Strategy", dashboard="Introduction"
              → would NOT modify (skill is additive only). Manual fix needed.
  Section 1 — LECTURE TITLE MISMATCH: plan="1.1 Welcome, Exam Format, ...", dashboard="Introduction"
              → would NOT modify. Manual fix needed.
  Section 2 — CREATE
    + Lecture 2.1 The Agentic Loop
    + Lecture 2.2 Prefilling
    ... (12 more)
  Section 3 — CREATE (12 lectures)
  Section 4 — CREATE (16 lectures)
  Section 5 — CREATE (15 lectures)
  Section 6 — CREATE (12 lectures)
  Section 7 — CREATE (17 lectures)

Total to create: 6 sections + 86 lectures
Manual fixes needed: 2 (Section 1 title + lecture rename)

To apply: re-run without --preview AND with --apply
To skip Section 1 mismatch warnings: use --sections=2,3,4,5,6,7
```
