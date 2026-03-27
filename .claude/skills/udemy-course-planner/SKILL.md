---
name: udemy-course-planner
description: >
  Plan and structure Udemy courses. Creates section structures, lecture title sequences,
  learning objectives, and folder scaffolding aligned with course-outline.md. Use when
  planning a new Udemy course, adding a new section, or restructuring existing content.
---

# Udemy Course Planner

## Overview

Plans and scaffolds Udemy course sections. Generates the directory tree, writes section
overview files with learning objectives, and creates lecture stubs ready to be filled
in by `udemy-lecture-writer`. The source of truth is always `course-outline.md`.

Udemy terminology:
- **Section** = a grouping of lectures (like Udacity's "Lesson")
- **Lecture** = an individual video (like Udacity's "Module Lecture")
- **Quiz** = knowledge check at the end of a section
- **Resource** = downloadable file (cheat sheet, PDF, reference table)
- **Lab** = scenario-based hands-on activity (linked from a section)

## Course Directory Convention

```
<course-name>/
├── course-outline.md                  # Source of truth — never deviate without updating this
├── study-guide.md                     # Comprehensive study material for reference
├── scripts/
│   ├── section-01-intro/
│   │   ├── section-overview.md
│   │   ├── 1.1-welcome-and-what-youll-learn.md
│   │   └── 1.2-exam-format-deep-dive.md
│   └── section-02-agentic-architecture/
│       ├── section-overview.md
│       └── 2.1-the-agentic-loop.md
├── slides/
│   └── section-02-agentic-architecture/   # Created when slides are generated
├── quizzes/
│   ├── section-01-exam-mechanics.md
│   └── section-02-agentic-architecture.md
├── labs/
│   ├── scenario-01-customer-support/
│   └── scenario-02-code-review/
└── resources/
    └── cheat-sheets/
        ├── domain-weights.md
        └── stop-reason-flow.md
```

## Workflow

### Step 1: Load Course Context

Before creating any files, read:
1. `course-outline.md` — section/lecture titles and structure
2. `study-guide.md` — domain details and exam concepts
3. Existing `scripts/` directory — what has already been written
4. Any domain-specific resource files in `resources/cheat-sheets/`

### Step 2: Determine Section Parameters

Confirm or determine:
- **Section number** (1-9 for Claude Architect course)
- **Section title** — from `course-outline.md`
- **Section slug** — kebab-case (e.g., `domain-1-agentic-architecture`)
- **Section folder** — `section-NN-slug` (zero-padded: `section-02`, not `section-2`)
- **Domain** — which CCA-F exam domain(s) this section covers
- **Exam weight** — percentage from the domain weights table
- **Lecture count** — from `course-outline.md`
- **Lecture titles** — from `course-outline.md`
- **Has quiz** — most sections (1-6, 8) have a section quiz
- **Has labs** — Sections 2-6 each have one or two scenario labs
- **Has resources** — downloadable cheat sheets for this section

### Step 3: Scaffold Directory Structure

Create the section folder under `scripts/` and any supporting directories:

```
scripts/section-NN-slug/
├── section-overview.md           # Created in Step 4
├── N.1-lecture-slug.md           # Stubs created in Step 5
├── N.2-lecture-slug.md
└── ...

quizzes/
└── section-NN-slug.md            # Stub created in Step 6 (if section has quiz)

labs/scenario-NN-slug/            # Created in Step 7 (if section has labs)
└── README.md
```

Naming rules:
- Section folders: `section-NN-slug` — two-digit zero-padded number
- Lecture files: `N.N-lecture-slug.md` — matches outline numbering (e.g., `2.1-`, `2.10-`, `2.14-`)
- Lecture slugs: kebab-case, max 50 chars, no special characters
- Quiz files: `section-NN-slug.md` inside `quizzes/`

### Step 4: Write section-overview.md

Create `scripts/section-NN-slug/section-overview.md`:

```markdown
# Section N: [Full Section Title]

## Overview
- **Domain**: [Domain name — e.g., Domain 1: Agentic Architecture & Orchestration]
- **Exam Weight**: [X%]
- **Lecture Count**: [N] lectures
- **Estimated Duration**: [X hours]

## Learning Objectives

By the end of this section, students will be able to:
- [Objective 1 — use Bloom's taxonomy verb: Apply, Design, Evaluate, Implement, Distinguish]
- [Objective 2]
- [Objective 3]
- [Objective 4 — max 5 objectives]

## Lectures

| # | Title | Duration | Status |
|---|-------|----------|--------|
| N.1 | [Title] | ~8 min | Todo |
| N.2 | [Title] | ~8 min | Todo |
...

## Quiz

Section quiz: `quizzes/section-NN-slug.md` (10 questions)

## Scenario Labs (if applicable)

| Lab | Scenario | File |
|-----|----------|------|
| Lab 1 | [Scenario name] | `labs/scenario-NN-slug/README.md` |

## Key Resources

| Resource | File |
|----------|------|
| [Cheat sheet name] | `resources/cheat-sheets/[file].md` |
```

### Step 5: Create Lecture Stub Files

For each lecture in the section, create `N.N-lecture-slug.md`:

```markdown
# Lecture N.N: [Full Lecture Title]

**Section**: [Section name] ([Domain weight if applicable])
**Estimated Duration**: 7-10 minutes
**Status**: Script stub — needs full script

## Key Points

[3-5 bullet points extracted from course-outline.md and study-guide.md]
- [Key concept 1]
- [Key concept 2]
- [Key concept 3]

## Script

> [TODO: Write full lecture script here]
>
> **Opening hook**: [What question or scenario draws students in?]
>
> **Core content**: [Walk through the key points above with examples]
>
> **Exam tip**: [What trap or pattern should students watch for?]
>
> **Closing**: [Summarize the one thing they must remember]

## Slide Notes

- [TODO: Key visuals or diagrams needed]
- [TODO: Code samples to show on screen]

## Demo/Screencast Notes

- [TODO: Any live demo or code walkthrough needed?]
```

Populate the **Key Points** section from study materials — don't leave it empty. This makes the stub immediately useful to `udemy-lecture-writer`.

### Step 6: Create Quiz Stub (if section has quiz)

Create `quizzes/section-NN-slug.md`:

```markdown
# Quiz: [Section Title]

> [TODO: Write quiz questions using udemy-quiz-creator skill]
>
> Target: 10 questions
> Types: Multiple choice (4 options, 1 correct), True/False, Multi-select
> Coverage: All lectures in this section, weighted toward exam-critical concepts
```

### Step 7: Create Lab Scaffold (if section has scenario labs)

For sections with scenario labs (Sections 2-6 in the Claude Architect course), create `labs/scenario-NN-slug/README.md`:

```markdown
# Scenario Lab: [Lab Title]

**Section**: Section N — [Domain name]
**Scenario**: [Which of the 6 exam scenarios this maps to]
**Status**: Scaffold — needs full lab content

## Objective

[1-2 sentences: what students build and why it demonstrates domain mastery]

## What You'll Build

- [Component 1]
- [Component 2]
- [Component 3]

## Steps

1. **Setup**: [Environment prerequisites]
2. **Core Build**: [Main implementation task]
3. **Test**: [How to verify it works]
4. **Extend**: [Optional stretch task]

## Key Concepts Demonstrated

- [Concept from lectures that this lab applies]
- [Another concept]

## Prerequisites

- Anthropic API key
- Node.js 18+ or Python 3.10+
- Claude Code CLI installed

## Resources

- Relevant lecture: [N.N — Lecture title]
- Reference: [Relevant cheat sheet or study guide section]
```

### Step 8: Validate

Before marking a section scaffold complete:

- [ ] `scripts/section-NN-slug/` folder exists
- [ ] `section-overview.md` has all required sections filled in
- [ ] All lectures from `course-outline.md` have stub files
- [ ] Lecture file names match `N.N-lecture-slug.md` pattern
- [ ] Lecture slugs are kebab-case, no special characters
- [ ] Key Points are populated from study materials (not empty)
- [ ] `quizzes/section-NN-slug.md` stub exists (if section has quiz)
- [ ] `labs/scenario-NN-slug/README.md` exists (if section has labs)
- [ ] Section overview lecture table matches the actual stub files created

## Key Rules

1. **course-outline.md = source of truth** — never change section/lecture titles without updating it first
2. **Zero-padded section numbers** — `section-01`, `section-02`, not `section-1`
3. **Lecture numbering matches outline** — `2.10` not `2.1.0`; use the exact N.N format from the outline
4. **Populate Key Points** — always extract 3-5 key points from study materials; empty stubs are unhelpful
5. **Bloom's taxonomy for objectives** — use action verbs: Apply, Evaluate, Design, Implement, Distinguish, Analyze, Compare
6. **No AWS/cloud content** — this is a Claude/Anthropic API course; no infrastructure scripts
7. **Exam-anchored** — every section overview states the domain weight and exam relevance
8. **Labs use real Anthropic SDK** — no mock APIs; students need an actual Anthropic API key
