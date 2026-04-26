---
name: udemy-lecture-description-writer
description: "Generate ~250-char Udemy lecture descriptions from course-outline.md titles, section-overview learning objectives, and per-lecture script Key Points. Writes course-metadata/lecture-descriptions.yaml keyed by section.lecture for the deployer to consume. Idempotent, no browser."
allowed-tools: Read, Glob, Grep, Write, Bash
---

# Udemy Lecture Description Writer

## Overview

Authors per-lecture marketing/curriculum descriptions for Udemy. Each description is
a single short paragraph (~250 chars, hard cap 250) that tells a student exactly what
they'll learn in that lecture. Output is a single YAML file at
`course-metadata/lecture-descriptions.yaml` keyed by `<section>.<lecture>` (e.g.
`"2.5"`). The sibling `udemy-lecture-description-deployer` skill consumes that file and
fills the per-lecture Description field in the Udemy instructor dashboard.

This skill never touches the browser. It is pure file output, idempotent, and safe to
re-run.

## When to use

- The user asks to "generate lecture descriptions" / "write Udemy descriptions" / "fill
  the description field for every lecture."
- A new lecture was added to `course-outline.md` and needs a description before the next
  deployer run.
- The author wants to regenerate a handful of stale descriptions.

## When NOT to use

- **Pushing descriptions into the Udemy dashboard** → `udemy-lecture-description-deployer`.
- **Authoring the lecture script itself** → `udemy-lecture-writer`.
- **Section-level descriptions / curriculum structure** → `udemy-course-planner`.

## Inputs

| Input | Path | Required | Used for |
|-------|------|----------|----------|
| Course outline | `course-outline.md` | yes | Section list + `N.M` lecture titles (regex `^(\d+)\.(\d+)\s+(.+?)$` under `### Lectures` headings) |
| Section overview | `scripts/section-NN-*/section-overview.md` | best-effort | Section context + Learning Objectives bullets |
| Per-lecture script | `scripts/section-NN-*/N.M-*.md` | best-effort | `## Key Points` block — concrete artifacts, APIs, rules to mention |
| Existing output | `course-metadata/lecture-descriptions.yaml` | best-effort | Idempotency — preserve hand-edited entries |

### Legacy folder mapping

The outline orders sections by exam-domain weight; the on-disk `scripts/` folders use a
legacy ordering. When loading section context, map outline section number → folder:

| Outline section | Filesystem folder |
|-----------------|-------------------|
| Section 1 | `scripts/section-01-intro/` |
| Section 2 | `scripts/section-02-api-bootcamp/` |
| Section 3 | `scripts/section-03-agentic-architecture/` |
| Section 4 | `scripts/section-05-claude-code-config/` |
| Section 5 | `scripts/section-06-prompt-engineering/` |
| Section 6 | `scripts/section-04-tool-design-mcp/` |
| Section 7 | `scripts/section-07-context-reliability/` |
| Sections 8–11 | no `scripts/` folder — use `labs/demos/demo-N-*/README.md` |

This mapping is also documented in `course-outline.md`'s Filesystem Note.

### Demo sections (8–11) auto-stub rule

Sections 8–11 have no `### Lectures` block in the outline. For each demo section, generate
two stub lectures:

- `N.1 Exercise` — student-facing prompt walkthrough
- `N.2 Solution Video` — instructor walkthrough of the worked solution

Source the demo objective + bullet list from `labs/demos/demo-N-*/README.md` (or the
"Walkthrough covers" block in the outline) for description context.

## Output

`course-metadata/lecture-descriptions.yaml`:

```yaml
descriptions:
  "1.1":
    title: "Welcome, Exam Format, Domains, Scenarios, Study Strategy & Exam-Guide Navigation"
    description: "Get oriented to the certification: scoring, the 5 domains and their weights, the 6 scenarios, and a study plan you can run in a single weekend or stretch over two weeks. The one lecture to watch first."
    char_count: 215
  "2.1":
    title: "The Messages API: Anatomy of a Request and Response"
    description: "Walk through every field in a Claude API request and response. By the end you'll know what `model`, `messages`, `max_tokens`, `system`, `stop_reason`, and `usage` actually mean — the foundation every other lecture in this section builds on."
    char_count: 244
  # ...95 entries total across Sections 1–11
```

Schema per entry:
- `title` — exact lecture title from `course-outline.md` (verbatim, including any colons / em-dashes)
- `description` — generated paragraph, ≤ 250 chars
- `char_count` — integer length of `description` (helps the deployer + author spot overruns)
- `needs_regeneration` — optional boolean. If `true`, the writer will overwrite this entry on the next `--missing` run. The author sets this by hand when a description is stale.

## Run modes

| Flag | Behavior |
|------|----------|
| `--all` (default) | Regenerate every entry. Overwrites existing `description` values. |
| `--lectures=2.1,2.5,3.10` | Regenerate only the listed entries (overwrite). |
| `--missing` | Generate only entries that are absent from the YAML or marked `needs_regeneration: true`. Never touches hand-edited entries. |
| `--dry-run` | Print the would-be YAML to stdout. Do not write the file. |

Default to `--missing` if the file already exists and the user did not specify a flag —
this is the safest mode. Use `--all` only when explicitly asked or when the file does not
yet exist.

## Workflow

### Step 1 — Parse the outline

Read `course-outline.md`. Build a planned tree:

- Iterate H2 `## Section N: …` headings → record section number, title.
- Inside each section, find the `### Lectures` heading and capture every line matching
  `^(\d+)\.(\d+)\s+(.+?)$` → record the lecture id (`N.M`) and title.
- For Sections 8–11, synthesize the two stub lectures (`Exercise` + `Solution Video`) per
  the auto-stub rule above. Use the section's H2 title + the "Walkthrough covers" block
  for context.

Total expected entries: 95 (verify and report a warning if the count differs).

### Step 2 — Load section context

For each section, try the legacy folder mapping above and read
`scripts/section-NN-*/section-overview.md`. Extract the bullets under
`## Learning Objectives` — these are the section-level claims you can lean on. If the file
does not exist (Sections 8–11), fall back to the H2-section description text in
`course-outline.md` plus the demo `README.md`.

### Step 3 — Load per-lecture context (best-effort)

Glob `scripts/section-NN-*/N.M-*.md` for each lecture id. If a file matches:

- Extract the `## Key Points` block (3–5 bullets). These are the concrete artifacts /
  APIs / rules the lecture covers — the highest-signal input for a description.
- If the file is a fully-written script (not a stub), also pull the SLIDE 1 narration
  (the opening hook) — useful for matching the lecture's actual angle.

If no file matches, fall back to title + section context only. Do not block on missing
script files — many lectures will not have one.

### Step 4 — Generate the description

For each lecture, draft a description that satisfies every rule in the next section.
Build the draft from:

1. The lecture title's keywords (the topic anchor).
2. 1–2 specific artifacts from the lecture's Key Points (e.g. `stop_reason`, `tool_choice`,
   `.claude/rules/`, `--output-format json`).
3. The section's domain context (where it earns its place in the section).

Then count characters. If > 250, tighten — drop adjectives and meta-phrases, never drop
the specific artifact names.

### Step 5 — Read existing YAML (idempotency)

If `course-metadata/lecture-descriptions.yaml` exists, parse it. For each planned entry:

- `--all` → always overwrite.
- `--lectures=…` → overwrite only the listed ids.
- `--missing` (default when file exists) → keep existing `description` unless the entry
  is absent OR `needs_regeneration: true`.
- Always refresh `title` from the outline (titles can drift; descriptions cannot be
  silently rewritten).
- Always recompute `char_count` from the final `description`.

### Step 6 — Write the YAML

Create `course-metadata/` if it does not exist. Write the file with:

- Stable key ordering: ascending numeric by `(section, lecture)`. `"2.10"` sorts after
  `"2.9"` numerically, not lexicographically — sort on the `(int, int)` tuple.
- Quote every key (`"1.1"` not `1.1`) so YAML never reads them as floats.
- 2-space indent. Always quote `description` values (they contain colons and em-dashes).

For `--dry-run`, print the same YAML to stdout and exit without writing.

### Step 7 — Report

Print a summary:

- Total entries written / preserved / skipped.
- Any descriptions over 240 chars (close to the cap — flag for human review).
- Any planned lectures that had no script file (so the author knows context was thinner).
- Path to the output file (or the dry-run banner).

## Generation rules (mandatory)

These are non-negotiable. Every description must satisfy every rule.

1. **≤ 250 characters.** Udemy's effective field cap is 280; the 30-char buffer
   absorbs em-dash escaping and trailing-period drift. Recount after every edit.

2. **Active voice, second person.** "You'll learn", "walk through", "by the end you'll
   know". Never "students will be able to" — that's a learning-objective register, not a
   marketing register.

3. **Lecture-specific, not section-generic.** The description must tell the student what
   *this* lecture covers that the *next* lecture does not. If you can swap the
   description between two lectures in the same section without anyone noticing, it is
   too generic. Rewrite.

4. **Mention the concrete artifact.** If the lecture is "3.1 The Agentic Loop:
   `stop_reason` Is Everything", the description must name `stop_reason` *and* the
   agentic loop. If it's "4.5 Path-Specific Rules with YAML Frontmatter Glob Patterns",
   it must name `paths:` (or `glob`) and `.claude/rules/`. Generic "agentic concepts" or
   "configuration patterns" fails this rule.

5. **Don't repeat the title verbatim.** The Udemy student already sees the title above
   the description. Repeating it wastes the budget. Allude to the title's terms but
   reframe them.

6. **No filler openings.** Banned: "This important lecture covers…", "We'll dive deep
   into…", "In this lecture, you will discover…", "Get ready to learn…". Open with a
   verb or a concrete promise.

7. **Use backticks for code identifiers.** `stop_reason`, `tool_choice`, `CLAUDE.md`,
   `.mcp.json`. The Udemy field renders Markdown for inline code.

8. **One sentence preferred, two acceptable, three only if needed.** Tight beats long.
   Periods, em-dashes, and colons are fine; semicolons feel academic — avoid.

9. **End with a payoff, not a transition.** The last clause should tell the student why
   they care: the trap they avoid, the artifact they ship, the question they can now
   answer. Never end with "…and more." or "…in the next lecture."

10. **Demo sections (8–11) — be honest about the format.** For `N.1 Exercise` describe
    the scenario the student will work through; for `N.2 Solution Video` explicitly
    frame it as a guided walkthrough of the worked solution (so the student does not
    expect new content).

## Idempotency contract

- The writer never silently rewrites a hand-edited description. The author's edits are
  protected by the absence of `needs_regeneration: true`.
- The writer always refreshes `title` and `char_count`. Title drift would otherwise
  cause the deployer to push a stale title; char_count drift would mask overruns.
- Re-running with no flags (`--missing` default) on a complete file is a no-op.

## Validation before exit

- [ ] Every entry's `char_count` matches `len(description)`.
- [ ] No `description` exceeds 250 chars.
- [ ] No `description` is a verbatim repeat of `title`.
- [ ] No `description` opens with a banned filler phrase.
- [ ] Entry count matches the parsed outline count (warn loudly on mismatch).
- [ ] YAML round-trips: re-read the file you just wrote and confirm `descriptions` is a
      mapping with the expected key set.

## Cross-references

- Sibling deployer: `udemy-lecture-description-deployer` (browser-driven, reads this
  file)
- Related authoring skill: `udemy-lecture-writer` (writes the script files this skill
  reads as context)
- Related authoring skill: `udemy-course-planner` (writes the section-overview files
  this skill reads as context)
- Source-of-truth input: `course-outline.md` in the course repo
