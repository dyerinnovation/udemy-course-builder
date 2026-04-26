# udemy-resource-uploader — Playbook

Operating reference for `[data-purpose="lecture-add-content-btn"]` →
'Resources' upload flow. Confirmed selectors are inherited from the
`udemy-curriculum-populator` playbook (same dashboard, same
`data-purpose` strategy). Resource-flow-specific selectors are TBD until
the first `--apply` run captures them.

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
dashboard. The public `/course/<slug>/` URL is for students and will not
work here.

## Confirmed selectors (inherited from curriculum-populator playbook)

Subset relevant to the resource-upload flow:

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A lecture row | `[data-purpose="lecture-editor"]` |
| Title text inside a lecture row | `[data-purpose="item-full-title"]` (innerText starts with `"Lecture N:"` — strip prefix to get the bare title) |
| Order/index inside a lecture row | `[data-purpose="item-object-index"]` (innerText is literally `"Lecture N:"`) |
| Inside a lecture row: open content-type picker | `[data-purpose="lecture-add-content-btn"]` |

Note: documented but **not** used by `udemy-curriculum-populator`. THIS
skill's flow starts with `lecture-add-content-btn`.

The picker behaviour mirrors the `add-item-inline` picker — sticky inline
expansion, NOT a popover. Clicking the same `lecture-add-content-btn`
again toggles it closed. Escape and outside-click do NOT close it.

## TBD — captured on first real `--apply` run

These selectors must be captured live during the first deployment, then
written into this table. The skill aborts on selector-drift rather than
guessing.

| Purpose | Likely selector (DO NOT trust until confirmed) |
|---|---|
| "Resources" sub-option in the content-type picker | `[data-purpose="resource-content-btn"]` (guess based on `add-coding-exercise-btn` / `add-lecture-btn` naming pattern) |
| File input for upload (likely hidden) | `input[type="file"]` scoped to the active picker; underlying `data-purpose` TBD |
| Upload progress indicator | TBD — likely a progress bar or spinner with a `data-purpose`-prefixed name |
| Upload-complete success indicator | TBD — likely a checkmark or the new attachment row appearing in the lecture's resource list |
| Existing attachment row (used for idempotency check) | TBD — possibly `[data-purpose="lecture-resource"]` or similar |
| Existing attachment filename text | TBD — child of the row above |
| Display-name rename input (after upload) | TBD — only relevant if Udemy exposes inline rename; may instead require an "Edit" affordance |
| Save / confirm rename button | TBD |
| External-resource (URL) sub-option (out of scope v1) | TBD |
| Validation error banner | `[role="alert"]` (assumption — verify) |

**Capture rule:** when the skill hits a TBD selector during `--apply`,
take a `read_page` / `browser_snapshot` immediately, dump the relevant
DOM subtree, abort, and update this table before retrying.

## DOM model — sections and lectures are SIBLINGS, not nested

Inherited from `udemy-curriculum-populator` playbook. Every curriculum
item (section row OR lecture row) is a direct child of
`[data-purpose="curriculum-list"]`, each wrapped in a
`div.js-curriculum-item-draggable.curriculum-list--list-item--xn0`.

To find a specific lecture (e.g. Section 2 / Lecture 2.1 = the 1st
`lecture-editor` after the Section 2 row):

1. Walk `curriculumList.children` in order.
2. Find the wrapper containing the matching
   `[data-purpose="section-editor"]` (use `item-object-index` text or the
   title to match).
3. Continue forward, counting `lecture-editor` wrappers until you reach
   the M-th one.
4. Stop when you hit the next wrapper containing a `section-editor`.

Reference enumeration (read-only) — same JS as the curriculum-populator
playbook:

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
      lectures: [],
      wrapper: w
    };
    result.push(currentSection);
  } else if (lec && currentSection) {
    const m = idxEl?.innerText.match(/Lecture\s+(\d+):/);
    currentSection.lectures.push({
      number: m ? `${currentSection.number}.${m[1]}` : null,
      title: titleEl?.innerText.replace(/^Lecture\s+\d+:\s*/, '').trim(),
      wrapper: w
    });
  }
});
JSON.stringify(result.map(s => ({...s, wrapper: undefined, lectures: s.lectures.map(l => ({...l, wrapper: undefined}))})), null, 2);
```

For the skill, keep the `wrapper` references (don't strip them as the
JSON dump above does) so subsequent steps can scope queries to the
chosen lecture.

## Idempotency check (per lecture, before upload)

Stub — the actual selectors are TBD until first capture. The shape:

```js
// EXAMPLE — selectors marked TBD must be replaced post-capture
function existingAttachmentFilenames(lectureWrapper) {
  // TBD: replace with the real per-row resource selector
  const rows = lectureWrapper.querySelectorAll('[data-purpose="lecture-resource"]');
  // TBD: replace with the real filename text selector
  return Array.from(rows).map(r =>
    r.querySelector('[data-purpose="resource-filename"]')?.innerText.trim()
  ).filter(Boolean);
}
```

Decision: if the planned file's basename (e.g. `CCA-CI-Study-Guide.pdf`)
appears in the returned list, SKIP unless `--force`. Match is exact,
case-sensitive — Udemy preserves the uploaded filename verbatim.

## Upload flow (per file)

1. **Locate the lecture wrapper** using the enumeration JS above. Keep the
   wrapper reference for scoping.

2. **Idempotency check.** Run `existingAttachmentFilenames(lectureWrapper)`
   (selectors TBD). Skip if match + no `--force`.

3. **Open the content-type picker.** Click the lecture's
   `[data-purpose="lecture-add-content-btn"]`. The picker expands inline.

4. **Click "Resources" sub-option.** Selector TBD on first capture
   (likely `[data-purpose="resource-content-btn"]`). Use selector-drift
   abort if zero matches.

5. **Locate the file input.** Selector TBD. Likely a hidden
   `input[type="file"]` revealed (or constructed) when the Resources
   sub-option is clicked. Search within the active picker subtree.

6. **Attach the file.** Use the active backend's file-upload primitive:
   - Playwright: `mcp__playwright__browser_file_upload` (which calls
     `setInputFiles` under the hood).
   - Chrome MCP: `mcp__Claude_in_Chrome__file_upload`.
   Pass the resolved absolute path. Do NOT click the visible "Upload"
   button — go straight to the input element.

7. **Wait for upload completion.** Poll for the progress indicator (TBD)
   to disappear AND the new attachment row to appear in the lecture's
   resource list. Hard timeout: 120s per file.

8. **Set display name (optional).** If `display_name` was provided AND
   Udemy exposes a rename input (TBD selector), set its value using the
   React-aware setter from the curriculum-populator playbook:
   ```js
   const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
   setter.call(input, newValue);
   input.dispatchEvent(new Event('input', { bubbles: true }));
   input.dispatchEvent(new Event('change', { bubbles: true }));
   ```
   Click save / confirm (TBD selector).

9. **Verify.** Re-read the lecture's attachment list; confirm the new
   filename is present. If not, screenshot + abort.

## Closing the picker without committing

The picker is sticky (same as `add-item-inline`). To dismiss it without
picking anything, click the SAME `lecture-add-content-btn` again
(toggles it closed). Do NOT rely on Escape or outside-click — neither
works.

## Worked example — `--preview` output

Input file `course-metadata/resources.yaml`:

```yaml
attachments:
  - section: 1
    lecture: 1.1
    files:
      - path: Claude-Created-Exam-Section-guides/CCA-CI-Study-Guide.pdf
        display_name: "Scenario 5: CI/CD Study Guide"
      - path: Claude-Created-Exam-Section-guides/CCA-Structured-Output-Study-Guide.pdf
        display_name: "Domain 4: Structured Output Study Guide"
```

Invocation:

```
udemy-resource-uploader \
  --course-id 7140821 \
  --course-repo ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --preview
```

Expected text output:

```
DRY RUN — udemy-resource-uploader
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course
Source: course-metadata/resources.yaml

Parsed plan (2 attachments across 1 lecture):
  Section 1 / Lecture 1.1 — "Welcome and What You'll Learn"
    + CCA-CI-Study-Guide.pdf (482 KB)
        display_name: "Scenario 5: CI/CD Study Guide"
    + CCA-Structured-Output-Study-Guide.pdf (1.1 MB)
        display_name: "Domain 4: Structured Output Study Guide"

File checks:
  ✓ All 2 source files exist
  ✓ No file exceeds 50MB threshold

Per-attachment dashboard flow (repeated for each file):
  [a] Read existing attachments on Lecture 1.1 (idempotency)
  [b] Click [data-purpose="lecture-add-content-btn"] on Lecture 1.1
  [c] Click "Resources" sub-option (selector TBD — first run captures)
  [d] Locate hidden file input (TBD)
  [e] setInputFiles(<absolute path to the PDF>)
  [f] Wait for upload-complete indicator (TBD), 120s timeout
  [g] Set display_name via rename input (TBD), save
  [h] Verify new attachment row present

Total to upload: 2 files (1.6 MB)
Lectures touched: 1
Existing attachments that would be SKIPPED: 0 (full read happens at apply time)

To apply: re-run without --preview AND with --apply
```
