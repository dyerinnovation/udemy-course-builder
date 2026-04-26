# udemy-lecture-description-deployer — Playbook

Operating reference for the
`[data-purpose="lecture-add-content-btn"]` → "Description" → textarea →
Save flow on `/manage/curriculum/`. Confirmed selectors are inherited from
`udemy-curriculum-populator/playbook.md` (recon 2026-04-26). Description-form
selectors (Description sub-option, textarea, Save) are TBD until the first
real `--apply` run captures them.

## Key insight: Udemy uses `data-purpose`

Same as `udemy-curriculum-populator` and `udemy-landing-populator`.
`data-purpose` attributes are stable across React re-renders and across UI
revs because they're semantic markers on Udemy's side, not generated class
names. **Prefer them over CSS class matches at every step.**

## URL

```
https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/
```

The instructor URL format uses a numeric course id, NOT the public slug.
Read the id from the URL while viewing the course in the instructor
dashboard.

## Confirmed selectors (inherited from udemy-curriculum-populator recon, 2026-04-26)

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A section row | `[data-purpose="section-editor"]` |
| A lecture row | `[data-purpose="lecture-editor"]` |
| Title text inside a section OR lecture row | `[data-purpose="item-full-title"]` |
| Order/index inside a section OR lecture row | `[data-purpose="item-object-index"]` (innerText is literally `"Section N:"` / `"Lecture N:"`) |
| Inside a lecture row: open the content-type picker (THIS skill's entry point) | `[data-purpose="lecture-add-content-btn"]` |

## TBD selectors — captured during first real `--apply` run

These are NOT yet captured. The selector-drift abort handler will surface
each one on first encounter — DO NOT guess. Update this table when each is
captured live:

| Purpose | Likely selector (UNVERIFIED) | Notes |
|---|---|---|
| "Description" sub-option in the content-type picker | `[data-purpose="add-description-btn"]` (assumption — verify) | Sibling of `add-coding-exercise-btn`, `add-quiz-btn`, etc. seen on the curriculum-item picker. The Description sub-flow lives on the LECTURE-LEVEL picker (`lecture-add-content-btn`), not the curriculum-item picker. Different DOM neighbourhood; selector unconfirmed. |
| Description form wrapper | `[data-purpose="description-form"]` | Pattern matches `section-form` / `lecture-form` in the populator's playbook. |
| Description textarea | `textarea` inside `[data-purpose="description-form"]` (no specific `data-purpose` confirmed yet) | Likely a single `<textarea>`, NOT a rich-text editor. Verify on first capture. |
| Save button | `[data-purpose="submit-description-form"]` | Pattern matches `submit-section-form` / `submit-lecture-form`. |
| Cancel button | `[data-purpose="cancel-description-form"]` | Pattern matches `cancel-section-form` / `cancel-lecture-form`. |
| Persisted description display (read-back for idempotency + verify) | TBD | Likely a content-summary node inside the lecture's expanded edit area, OR a hover-tooltip. Capture during first read pass. |
| Validation error banner | `[role="alert"]` (assumption — same as populator) | Verify. |
| Character-limit hint (Udemy may cap at ~1000–2000 chars) | TBD | Capture if surfaced. |

## DOM model — sections and lectures are SIBLINGS, not nested

This is the most important correction inherited from
`udemy-curriculum-populator/playbook.md`. Every curriculum item (section row
OR lecture row) is a direct child of `[data-purpose="curriculum-list"]`,
each wrapped in a `div.js-curriculum-item-draggable.curriculum-list--list-item--xn0`.
Lectures are NOT nested inside sections in the DOM.

To find the lecture matching a YAML key like `"2.5"`:
1. Walk `curriculumList.children` in order.
2. Track which `[data-purpose="section-editor"]` is the current section
   header (parse the integer from `[data-purpose="item-object-index"]`'s
   innerText `"Section N:"`).
3. Within each section, count consecutive `[data-purpose="lecture-editor"]`
   wrappers. The Nth lecture in section M maps to YAML key `"M.N"`.
4. Stop at the next wrapper containing a `[data-purpose="section-editor"]`.

Reference enumeration (read-only — adapted from the populator's flat-DOM
walk):

```js
const list = document.querySelector('[data-purpose="curriculum-list"]');
const wrappers = list.querySelectorAll(':scope > div.js-curriculum-item-draggable, :scope > div.curriculum-list--list-item--xn0');
const lectureMap = {};   // "2.5" → wrapper element
let currentSection = null;
let lectureIdx = 0;
wrappers.forEach(w => {
  const sec = w.querySelector('[data-purpose="section-editor"]');
  const lec = w.querySelector('[data-purpose="lecture-editor"]');
  const idxEl = w.querySelector('[data-purpose="item-object-index"]');
  if (sec) {
    const m = idxEl?.innerText.match(/Section\s+(\d+):/);
    currentSection = m ? Number(m[1]) : null;
    lectureIdx = 0;
  } else if (lec && currentSection != null) {
    lectureIdx += 1;
    lectureMap[`${currentSection}.${lectureIdx}`] = w;
  }
});
JSON.stringify(Object.keys(lectureMap));
```

Note: lecture numbering in the dashboard is per-section (`Lecture 1:`,
`Lecture 2:`, etc. restart at 1 within each section), NOT the dotted `2.5`
form used in the YAML and `course-outline.md`. The skill reconciles by
mapping position-within-section: YAML key `"2.5"` matches the 5th
`lecture-editor` under Section 2.

## Description fill flow (per lecture)

1. **Locate the lecture wrapper** by YAML key (use `lectureMap` from the
   enumeration above).

2. **Click the lecture's `[data-purpose="lecture-add-content-btn"]`**:
   ```js
   const wrapper = lectureMap['2.5'];
   const btn = wrapper.querySelector('[data-purpose="lecture-add-content-btn"]');
   btn.click();
   ```
   This toggles a sticky-inline content-type picker (NOT a popover; same
   pattern as `add-item-inline`). Clicking the same button again collapses
   it. Escape and outside-click do NOT close it.

3. **Click the "Description" sub-option** (selector TBD — the
   selector-drift handler must capture on first run). Best-guess:
   `[data-purpose="add-description-btn"]`. If absent, dump the whole picker
   subtree to a screenshot and abort.

4. **Locate the description textarea** (selector TBD — likely a single
   `<textarea>` inside `[data-purpose="description-form"]`).

5. **Fill the textarea using the React value-setter pattern.** Udemy's
   React-controlled inputs IGNORE `textarea.value = "..."` — they read from
   React's internal state, which is updated by the native setter +
   dispatched events. Use this snippet (the same pattern documented in
   `udemy-curriculum-populator/playbook.md` for `<input>`, adapted for
   `<textarea>`):

   ```js
   const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
   setter.call(textarea, descriptionText);
   textarea.dispatchEvent(new Event('input', { bubbles: true }));
   textarea.dispatchEvent(new Event('change', { bubbles: true }));
   ```

   After this snippet runs, React's controlled state matches the textarea
   DOM value AND the Save button transitions from disabled to enabled.

6. **Click Save** (selector TBD — likely
   `[data-purpose="submit-description-form"]`). The form should disappear
   within ~1s and the description should appear in the lecture's metadata
   area.

7. **Verify byte-for-byte.** Re-read the persisted description (selector
   TBD per the read-back row in the table above) and assert
   `dashboardText.trim() === yamlText.trim()`. Mismatch = ABORT (could be
   character-limit truncation, stale picker click, or selector drift).

## Closing the picker without committing

The picker is sticky. To dismiss it without picking anything, click the
ORIGINAL `lecture-add-content-btn` again (toggles it closed). Do NOT rely
on Escape or outside-click — neither works.

## Worked example — `--preview` output for 3 sample lectures

YAML (`course-metadata/lecture-descriptions.yaml`):

```yaml
"2.1":
  description: "Walk through the agentic loop end-to-end: the four-stage cycle of prompt → response → tool call → tool result that powers every Claude agent."
"2.2":
  description: "Why prefilling matters and when to reach for it. Includes the JSON-coercion trick and the 'don't prefill the wrong character' trap."
"2.5":
  description: "Stop reasons gate every agentic loop iteration. We cover end_turn, tool_use, max_tokens, and stop_sequence — and what to do on each."
```

Invocation:

```
udemy-lecture-description-deployer \
  --course-id 7140821 \
  --course-repo ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --preview
```

Expected text output:

```
DRY RUN — udemy-lecture-description-deployer
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
YAML: ~/Documents/dev/udemy-courses/claude-architect-udemy-course/course-metadata/lecture-descriptions.yaml

Parsed plan from YAML (3 lectures):
  2.1 The Agentic Loop                       (description: 156 chars)
  2.2 Prefilling                             (description: 138 chars)
  2.5 Stop Reasons & Branching               (description: 152 chars)

Existing curriculum (read from dashboard):
  2.1 The Agentic Loop                       → description: empty
  2.2 Prefilling                             → description: 138 chars (identical to YAML)
  2.5 Stop Reasons & Branching               → description: 124 chars
                                               "Walk through stop_reason values and how to branch on each."

Diff:
  Lecture 2.1 → CREATE
    + "Walk through the agentic loop end-to-end: the four-stage cycle..."
  Lecture 2.2 → MATCH (skip; re-run with --force=2.2 to re-write)
  Lecture 2.5 → OVERWRITE (requires --force)
    - dashboard: "Walk through stop_reason values and how to branch on each."
    + YAML:      "Stop reasons gate every agentic loop iteration..."

Summary:
  CREATE: 1   MATCH: 1   OVERWRITE (blocked, needs --force): 1
  Net writes without --force: 1
  Net writes with --force:    2 (creates 2.1, overwrites 2.5)

To apply: re-run without --preview
To overwrite divergent entries: re-run with --force
```
