---
name: udemy-quiz-creator
description: >
  Create quizzes, practice tests, and knowledge checks for Udemy certification prep
  courses. Generates section quizzes (10 questions) and the full 40-question practice
  exam. Questions are scenario-based, with detailed explanations and distractor analysis.
  Use when building a section quiz, extending an existing quiz, or creating the practice exam.
---

# Udemy Quiz Creator

## Overview

Creates quiz content for Udemy certification prep courses. Output is a markdown file
with fully written questions, all answer options, correct answer keys, detailed
explanations, and distractor analysis. Designed for the Claude Certified Architect
(CCA-F) course but adaptable to any exam prep course.

Key conventions:
- **No upload automation** — Udemy quiz upload is done manually in the Instructor dashboard
- **Udemy question types** — Multiple Choice (4 options, 1 correct), True/False, Multi-Select
- **Scenario-based framing** — questions present real architectural decisions, not trivia
- **Distractor analysis** — explanations say why each wrong answer is wrong (not just why the right answer is right)

## Question Types

### Multiple Choice (MC)
Single correct answer, 3 plausible distractors. Most common type.
```
## Question N
**[Question text]**

- A) [Option A]
- B) [Option B]
- C) [Option C]
- D) [Option D]

**Correct Answer**: [Letter]
**Explanation**: [Why correct answer is right. Why each distractor is wrong.]
**Domain**: [Domain name and number]
```

### True/False (TF)
Simple binary. Use sparingly — only for definitional or absolute rules.
```
## Question N
**[Statement]** True or False?

- A) True
- B) False

**Correct Answer**: [A or B]
**Explanation**: [Why this is true/false. Common misconception that makes the wrong answer tempting.]
**Domain**: [Domain name]
```

### Multi-Select (MS)
Multiple correct answers (2-4 correct out of 5 options). Use for "select all that apply" concepts.
```
## Question N
**[Question text] (Select all that apply.)**

- A) [Option A]
- B) [Option B]
- C) [Option C]
- D) [Option D]
- E) [Option E]

**Correct Answers**: [Letters, e.g., A, C, D]
**Explanation**: [Why each correct answer is right. Why each wrong answer is wrong.]
**Domain**: [Domain name]
```

## Section Quiz Workflow

### Step 1: Load Lecture Content

Before writing any questions, read:
1. All lecture scripts in the section's `scripts/section-NN-slug/` folder
2. The section overview file for learning objectives
3. Relevant cheat sheet files in `resources/cheat-sheets/`
4. The `study-guide.md` for sample questions and exam context

### Step 2: Identify Testable Concepts

List every distinct concept covered in the section's lectures. Tag each as:
- **High priority** — appears in Domain 1-4 (27%/20%/20%/18%) and is scenario-testable
- **Medium priority** — definitional or supporting concept
- **Low priority** — contextual detail unlikely to appear on the exam

### Step 3: Plan Question Distribution

For a 10-question section quiz:
- **7 Multiple Choice** — the workhorse format
- **1 True/False** — pick a "sounds plausible but wrong" definitional claim
- **2 Multi-Select** — use for categories (error types, tool choice options, config levels)

For the 40-question practice exam:
- **28 Multiple Choice**
- **4 True/False**
- **8 Multi-Select**
- **Domain distribution** (weighted): Domain 1: 11q, Domain 3: 8q, Domain 4: 8q, Domain 2: 7q, Domain 5: 6q

### Step 4: Write Questions

**Question quality checklist** (apply to each question):
- [ ] **Scenario-framed** — at least 50% of questions should present a situation, not ask "what is X?"
- [ ] **Unambiguous** — exactly one best answer; if two options could be right, the question is broken
- [ ] **Plausible distractors** — wrong answers reflect real misconceptions, not obviously silly choices
- [ ] **Correct answer randomized** — don't put all correct answers in position A or C
- [ ] **Difficulty varies** — mix straightforward recall (30%) with judgment/application (70%)
- [ ] **Domain tagged** — every question has a Domain tag for post-quiz analysis

### Step 5: Write Explanations

Every question requires an explanation that:
1. States **why the correct answer is right** (one sentence)
2. Addresses **why each distractor is wrong** (one sentence each)
3. Cites the **relevant rule or pattern** from the course content

Strong explanation example:
> **Correct Answer**: C
> **Explanation**: When stop_reason is "end_turn", the agent has completed its reasoning
> and the loop must stop — the control flow exits. (A) is wrong because "tool_use" is what
> triggers continued looping, not "end_turn". (B) is wrong because stop_reason has nothing
> to do with error state — errors are handled through tool result content. (D) is wrong
> because these two stop_reason values have entirely different control flow implications.
> **Domain**: Domain 1 - Agentic Architecture

### Step 6: Validate

Before finalizing a quiz:
- [ ] Total question count matches target (10 for section, 40 for practice exam)
- [ ] Type distribution is correct (MC/TF/MS ratios)
- [ ] Every question has: question text, all options, correct answer, explanation, domain tag
- [ ] At least 50% of questions are scenario-framed
- [ ] Correct answer positions vary (not all A or all C)
- [ ] Multi-select questions specify "(Select all that apply.)"
- [ ] Multi-select explanations address each option individually
- [ ] No factual errors — verify against study-guide.md and cheat sheets
- [ ] Domain distribution is weighted correctly (practice exam only)

## Domain-Specific Question Patterns (Claude Architect Course)

### High-Probability Topics by Domain

**Domain 1 — Agentic Architecture (27%)**
- stop_reason: "tool_use" → continue loop, "end_turn" → stop
- allowedTools must include "Task" for subagent spawning
- Parallel subagents: ALL spawned in a single response (one coordinator turn)
- Programmatic vs prompt enforcement decision rule
- PostToolUse hooks for normalizing heterogeneous tool responses
- Session management: --resume vs fork_session vs new session

**Domain 2 — Tool Design & MCP (18%)**
- tool_choice: "auto" (model decides), "any" (must call a tool), {"type":"tool","name":"X"} (specific tool)
- Error categories: transient (isRetryable: true), validation/business/permission (isRetryable: false)
- Required error fields: errorCategory, isRetryable, description
- Empty result ({"result":[]}) vs error response — distinct concepts
- MCP scope: project-level (.mcp.json in repo) vs user-level (~/.claude.json)
- MCP resources (static data) vs MCP tools (actions)

**Domain 3 — Claude Code Config (20%)**
- CLAUDE.md hierarchy: user > project > directory (most specific wins)
- @import syntax for modular CLAUDE.md files
- .claude/rules/ with YAML frontmatter glob patterns for path-specific rules
- context: fork — skill runs in isolated context, doesn't pollute main conversation
- -p flag for non-interactive CI usage
- Plan mode vs direct execution decision framework

**Domain 4 — Prompt Engineering (20%)**
- tool_choice: "any" guarantees a tool call (structured output enforcement)
- Few-shot examples: use when Claude makes systematic errors on ambiguous inputs
- Message Batches API: 50% savings, up to 24h window, NO multi-turn tool use
- Validation-retry loops: effective for syntax errors, NOT for systematic semantic errors
- Multi-instance review: independent Claude instance beats self-review
- detected_pattern field for false positive analysis

**Domain 5 — Context Management (15%)**
- "Lost in the middle" effect: middle-of-context information is least attended to
- Escalation triggers: policy gap, explicit customer request, or stuck — NOT frustration
- Empty result vs access failure distinction
- Structured error propagation across multi-agent systems
- Persistent "case facts" block pattern for customer support agents

## Distractor Design Guide

Distractors should represent real misconceptions, not obvious wrong answers. Common patterns:

| Trap Pattern | Example |
|-------------|---------|
| **Partially right** | "isRetryable is set in the tool response" (true structure, wrong field) |
| **Right concept, wrong domain** | "Use Message Batches for real-time responses" (right API, wrong use case) |
| **Plausible but opposite** | "empty result means the query failed" (confident, wrong) |
| **Over-engineered** | "Always use programmatic enforcement" (never vs sometimes) |
| **Under-specified** | "tool_choice: auto" when the question requires a tool call |
| **Confusing scope** | "Put shared team MCP servers in ~/.claude.json" (personal scope, not shared) |

## File Format

### Section Quiz Header
```markdown
# Quiz: [Section Title or Domain Name]

**Section**: Section N — [Full section title]
**Domain**: [Domain N — Name] ([Weight]%)
**Questions**: [N]

---
```

### Practice Exam Header
```markdown
# Practice Exam: Claude Certified Architect – Foundations (CCA-F)

**Total Questions**: 40
**Passing Score Reference**: 720/1000 (72%)
**Domain Distribution**:
- Domain 1 (Agentic Architecture, 27%): 11 questions
- Domain 2 (Tool Design & MCP, 18%): 7 questions
- Domain 3 (Claude Code Config, 20%): 8 questions
- Domain 4 (Prompt Engineering, 20%): 8 questions
- Domain 5 (Context & Reliability, 15%): 6 questions

---
```

## Exam Accuracy Notes (CCA-F)

Always verify against these authoritative values before finalizing:

| Fact | Correct Value |
|------|---------------|
| Passing score | 720 out of 1000 |
| Domain 1 weight | 27% |
| Domain 2 weight | 18% |
| Domain 3 weight | 20% |
| Domain 4 weight | 20% |
| Domain 5 weight | 15% |
| Scenarios presented | 6 |
| Scenarios to complete | 4 of 6 |
| Penalty for wrong answer | None |
| tool_choice options | "auto", "any", {"type":"tool","name":"X"} |
| Error categories | transient, validation, business, permission |
| Batch API savings | 50% off sync pricing |
| Batch API window | Up to 24 hours |

**Note**: The exam emphasizes judgment and architectural decision-making over API syntax memorization. Write questions that test "when to use X vs Y" rather than "what is the definition of X."
