# Udemy Course Builder — Claude Code Plugin

A Claude Code plugin providing four skills for building Udemy course content: section planning, lecture writing, slide generation, and quiz creation.

## Project Context

- **Author:** Jonathan Dyer / Dyer Innovation
- **Plugin manifest:** `plugin.json` (root) and `.claude/skills/plugin.json`
- **Brand assets:** Dyer Innovation design system (green/teal palette, see slide-creator SKILL.md)

## Skills

- `udemy-course-planner` — Plans sections, scaffolds folders, writes section overviews and lecture stubs
- `udemy-lecture-writer` — Writes complete lecture scripts with SLIDE markers, visual descriptions, and exam tips
- `udemy-slide-creator` — Generates branded .pptx slides from lecture scripts using python-pptx
- `udemy-quiz-creator` — Creates section quizzes and practice exams in Udemy-compatible formats

## Rules

@.claude/rules/
