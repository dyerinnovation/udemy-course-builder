# Course Creation Workflow

The skills are designed to be used in sequence:

1. **udemy-course-planner** — Start here. Plans sections and creates folder scaffolding.
2. **udemy-lecture-writer** — Write lecture scripts for each planned lecture.
3. **slidev-runner** — Create Slidev markdown presentations from lecture scripts. **Preferred slide format** as of 2026-03 (slide.dev won the slide framework eval). Output goes in `<course-dir>/slidev/lecture-N.M.md`.
4. **udemy-quiz-creator** — Create quizzes after each section's lectures are finalized.

**Legacy:** `udemy-slide-creator` generates `.pptx` files via python-pptx. Use only if a PowerPoint file is explicitly required. Slidev is preferred for all new slide work.

Each skill's SKILL.md contains detailed usage instructions and trigger conditions.
