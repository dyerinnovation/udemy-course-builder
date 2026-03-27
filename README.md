# Udemy Course Builder

A Claude Code plugin for building Udemy course content. Provides four skills that work together to plan, write, design, and quiz-ify your courses.

## Skills

| Skill | Purpose |
|-------|---------|
| `udemy-course-planner` | Plan sections, scaffold folders, create outlines |
| `udemy-lecture-writer` | Write complete lecture scripts with slide markers |
| `udemy-slide-creator` | Generate branded .pptx slides from lecture scripts |
| `udemy-quiz-creator` | Create section quizzes and practice exams |

## Installation

Install as a Claude Code plugin:

```bash
claude plugin add dyerinnovation/udemy-course-builder
```

## Usage

The skills are designed to be used in sequence: plan → write → slides → quiz. Each skill triggers automatically based on context, or you can invoke them directly.

## Brand

All generated content follows the Dyer Innovation design system (green/teal palette). See the slide-creator skill for the full color and typography spec.

## Author

Jonathan Dyer / [Dyer Innovation](https://github.com/dyerinnovation)
