#!/usr/bin/env python3
"""udemy-video-uploader — STUB v0

Upload rendered lecture .mp4 files into Udemy lecture stubs via Chrome MCP /
Playwright browser automation.

This is a stub-level entrypoint. Argparse plumbing, MP4 path resolution,
preflight validation, and dry-run plan output are real. The Chrome MCP /
Playwright invocations themselves are TODOs with detailed pseudo-code
describing the exact selectors + events to drive when this is fleshed out.

Mirrors udemy-resource-uploader's structure. See SKILL.md and playbook.md
for the operator-facing reference.

Typical invocation:

    python upload.py \\
        --course-id 7140821 \\
        --course-root ~/Documents/dev/udemy-courses/claude-architect-udemy-course \\
        --lectures 2.1,2.2,2.3 \\
        --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTRUCTOR_CURRICULUM_URL = (
    "https://www.udemy.com/instructor/course/{course_id}/manage/curriculum/"
)

# Default MP4 location relative to the course root. Overridable via --mp4-dir.
DEFAULT_MP4_SUBDIR = "artifacts/lectures"

# Sanity thresholds
UDEMY_HARD_LIMIT_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB (Udemy's stated max)
SOFT_WARN_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB (practical wobble in our experience)
DEFAULT_TRANSCODE_TIMEOUT_SEC = 300

# Heuristic: per-lecture run > N → pause to confirm before continuing
PAUSE_AND_CONFIRM_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class LecturePlan:
    """One lecture targeted by this run."""

    number: str                 # "2.1"
    section: int                # 2
    index_in_section: int       # 1 (the "1" in "2.1")
    title: Optional[str]        # resolved from course-outline.md if present
    mp4_path: Path              # absolute path to the rendered MP4
    mp4_exists: bool = False
    size_bytes: int = 0
    duration_sec: Optional[float] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class RunPlan:
    course_id: str
    course_root: Path
    mp4_dir: Path
    backend: str                # "chrome" | "playwright"
    lectures: list[LecturePlan]
    force_replace: bool
    transcode_timeout_sec: int
    dry_run: bool


# ---------------------------------------------------------------------------
# Logging — keep it tiny and human-readable; no third-party deps
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    print(f"[udemy-video-uploader] {msg}", flush=True)


def abort(msg: str, code: int = 1) -> None:
    print(f"[udemy-video-uploader] ABORT: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="udemy-video-uploader",
        description=(
            "Upload rendered lecture .mp4 files into Udemy lecture stubs via "
            "Chrome MCP / Playwright. STUB v0 — see SKILL.md."
        ),
    )
    p.add_argument(
        "--course-id",
        required=True,
        help="Numeric Udemy course id (from the instructor URL).",
    )
    p.add_argument(
        "--course-root",
        required=True,
        type=Path,
        help="Absolute path to the course repo root.",
    )

    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--lectures",
        help="Comma-separated lecture numbers, e.g. '2.1,2.2,2.3'.",
    )
    target.add_argument(
        "--section",
        type=int,
        help="Upload every lecture in this section (resolves from course-outline.md).",
    )
    target.add_argument(
        "--all",
        action="store_true",
        help="Upload every lecture in the course (use with care).",
    )

    p.add_argument(
        "--mp4-dir",
        type=Path,
        default=Path(DEFAULT_MP4_SUBDIR),
        help=(
            "Directory containing lecture-X.Y.mp4 files (relative to "
            f"--course-root, default '{DEFAULT_MP4_SUBDIR}')."
        ),
    )
    p.add_argument(
        "--dry-run",
        "--preview",
        dest="dry_run",
        action="store_true",
        help="Print the action plan WITHOUT opening the browser.",
    )
    p.add_argument(
        "--force-replace",
        action="store_true",
        help=(
            "Replace any existing video on the target lecture(s). "
            "Destructive — prompts before each replacement."
        ),
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Required on re-runs when the default is report-only.",
    )
    p.add_argument(
        "--transcode-timeout",
        type=int,
        default=DEFAULT_TRANSCODE_TIMEOUT_SEC,
        help=(
            "Per-lecture max wait (sec) for Udemy server-side transcoding "
            f"before aborting. Default {DEFAULT_TRANSCODE_TIMEOUT_SEC}s."
        ),
    )
    p.add_argument(
        "--backend",
        choices=("chrome", "playwright"),
        default="chrome",
        help="Browser automation backend.",
    )
    return p


# ---------------------------------------------------------------------------
# Lecture resolution
# ---------------------------------------------------------------------------


_LECTURE_NUM_RE = re.compile(r"^\s*(\d+)\.(\d+)\s*$")


def _split_lecture_number(num: str) -> tuple[int, int]:
    m = _LECTURE_NUM_RE.match(num)
    if not m:
        abort(f"Invalid lecture number '{num}' — expected 'N.M' format.")
    return int(m.group(1)), int(m.group(2))


def _parse_course_outline(outline_path: Path) -> dict[int, list[tuple[int, str]]]:
    """Return {section_number: [(lecture_index, lecture_title), ...]}.

    Minimal parser — looks for:
      ## Section N: <title>
      ...
      ### Lecture N.M: <title>     (or numbered list "N.M <title>")
    Tolerant of variations. Returns empty section list for sections with no
    detected lectures (so --section can still resolve them by index).
    """
    if not outline_path.exists():
        return {}

    out: dict[int, list[tuple[int, str]]] = {}
    current_section: Optional[int] = None

    section_re = re.compile(r"^##\s+Section\s+(\d+)\s*[:\-]\s*(.+)$", re.IGNORECASE)
    # Match "### Lecture N.M: title" OR "N.M title" in a numbered list
    lecture_re_head = re.compile(
        r"^###\s+Lecture\s+(\d+)\.(\d+)\s*[:\-]\s*(.+)$", re.IGNORECASE
    )
    lecture_re_list = re.compile(r"^\s*(\d+)\.(\d+)\s+(.+)$")

    for raw in outline_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = section_re.match(line)
        if m:
            current_section = int(m.group(1))
            out.setdefault(current_section, [])
            continue
        if current_section is None:
            continue
        m = lecture_re_head.match(line)
        if not m:
            m = lecture_re_list.match(line)
        if m:
            sec_n = int(m.group(1))
            lec_n = int(m.group(2))
            title = m.group(3).strip().rstrip(".")
            # Only record if it matches the active section
            if sec_n == current_section:
                out.setdefault(sec_n, []).append((lec_n, title))
    return out


def _resolve_target_lectures(
    args: argparse.Namespace,
    course_outline: dict[int, list[tuple[int, str]]],
) -> list[tuple[int, int, Optional[str]]]:
    """Return [(section, index_in_section, title?), ...] in upload order."""
    targets: list[tuple[int, int, Optional[str]]] = []

    if args.lectures:
        for raw in args.lectures.split(","):
            sec, lec = _split_lecture_number(raw)
            title = None
            for ln, ltitle in course_outline.get(sec, []):
                if ln == lec:
                    title = ltitle
                    break
            targets.append((sec, lec, title))
    elif args.section is not None:
        sec_lectures = course_outline.get(args.section)
        if not sec_lectures:
            abort(
                f"--section {args.section} resolved to zero lectures in "
                f"course-outline.md. Check the outline or use --lectures."
            )
        for lec_n, title in sec_lectures:
            targets.append((args.section, lec_n, title))
    elif args.all:
        if not course_outline:
            abort("--all requires a parseable course-outline.md; none found.")
        for sec_n in sorted(course_outline):
            for lec_n, title in course_outline[sec_n]:
                targets.append((sec_n, lec_n, title))

    if not targets:
        abort("No lectures resolved from the supplied flags.")
    return targets


# ---------------------------------------------------------------------------
# MP4 validation
# ---------------------------------------------------------------------------


def _probe_duration_sec(mp4: Path) -> Optional[float]:
    """Use ffprobe if available; return None if unavailable or on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(mp4),
            ],
            check=True, capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return None


def _build_lecture_plan(
    section: int,
    lec_index: int,
    title: Optional[str],
    mp4_dir_abs: Path,
) -> LecturePlan:
    number = f"{section}.{lec_index}"
    mp4_path = mp4_dir_abs / f"lecture-{number}.mp4"
    plan = LecturePlan(
        number=number,
        section=section,
        index_in_section=lec_index,
        title=title,
        mp4_path=mp4_path,
    )
    if mp4_path.exists() and mp4_path.is_file():
        plan.mp4_exists = True
        plan.size_bytes = mp4_path.stat().st_size
        plan.duration_sec = _probe_duration_sec(mp4_path)
        if plan.size_bytes == 0:
            plan.warnings.append("MP4 is 0 bytes — refusing to upload.")
        if plan.size_bytes > UDEMY_HARD_LIMIT_BYTES:
            plan.warnings.append(
                f"MP4 size {plan.size_bytes / 1e9:.2f} GB exceeds Udemy 4GB hard limit."
            )
        elif plan.size_bytes > SOFT_WARN_BYTES:
            plan.warnings.append(
                f"MP4 size {plan.size_bytes / 1e9:.2f} GB — large, may upload slowly."
            )
        if plan.duration_sec is not None and plan.duration_sec <= 0:
            plan.warnings.append("MP4 duration reads as 0 — likely corrupt.")
    return plan


# ---------------------------------------------------------------------------
# Plan / report rendering
# ---------------------------------------------------------------------------


def _fmt_size(n_bytes: int) -> str:
    if n_bytes >= 1e9:
        return f"{n_bytes / 1e9:.2f} GB"
    if n_bytes >= 1e6:
        return f"{n_bytes / 1e6:.1f} MB"
    if n_bytes >= 1e3:
        return f"{n_bytes / 1e3:.1f} KB"
    return f"{n_bytes} B"


def _fmt_duration(sec: Optional[float]) -> str:
    if sec is None:
        return "?:??"
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}m {s:02d}s"


def print_plan(plan: RunPlan) -> None:
    log("")
    log("=== PLAN ===")
    log(f"Target: {INSTRUCTOR_CURRICULUM_URL.format(course_id=plan.course_id)}")
    log(f"Course root: {plan.course_root}")
    log(f"MP4 dir: {plan.mp4_dir}")
    log(f"Backend: {plan.backend}")
    log(f"Force replace: {plan.force_replace}")
    log(f"Transcode timeout: {plan.transcode_timeout_sec}s")
    log("")
    log(f"Resolved {len(plan.lectures)} lecture(s):")
    missing = 0
    for lec in plan.lectures:
        title_str = f' — "{lec.title}"' if lec.title else ""
        log(f"  Section {lec.section} / Lecture {lec.number}{title_str}")
        if lec.mp4_exists:
            log(
                f"    file: {lec.mp4_path.relative_to(plan.course_root) if lec.mp4_path.is_relative_to(plan.course_root) else lec.mp4_path} "
                f"({_fmt_size(lec.size_bytes)}, {_fmt_duration(lec.duration_sec)}) OK"
            )
        else:
            missing += 1
            log(f"    file: {lec.mp4_path} — MISSING")
        for w in lec.warnings:
            log(f"    warning: {w}")
    log("")
    log("File checks:")
    if missing:
        log(f"  {missing} MP4 missing — fix before applying.")
    else:
        log(f"  All {len(plan.lectures)} MP4(s) present.")
    log("")
    log("Per-lecture dashboard flow (would repeat for each found file):")
    log('  [a] Check lecture row for existing video-icon (idempotency)')
    log('  [b] Click [data-purpose="lecture-add-content-btn"]')
    log('  [c] Click [data-purpose="select-video"] '
        '(or replace-with-video if --force-replace)')
    log('  [d] Locate hidden <input type="file" name="file"> (TBD — verify on first run)')
    log('  [e] setInputFiles(<absolute path to MP4>)')
    log(f'  [f] Wait for upload + transcode complete '
        f'(Save button enabled), {plan.transcode_timeout_sec}s timeout')
    log('  [g] Click Save')
    log('  [h] Verify video-icon present on lecture row')
    log("")


# ---------------------------------------------------------------------------
# Browser flow — STUB. Real selectors + invocations land on first --apply run.
# ---------------------------------------------------------------------------


def _ensure_auth(plan: RunPlan) -> None:
    """Verify browser auth is ready before navigating anywhere."""
    # TODO(impl): chrome backend
    #   - call mcp__Claude_in_Chrome__list_connected_browsers
    #   - if no browser, abort with the Option A setup pointer (see SKILL.md)
    #   - if multiple browsers, prompt the user to pick
    # TODO(impl): playwright backend
    #   - require ~/.config/udemy-deployer/auth.json
    #   - abort with Option B setup command if missing
    log(f"[stub] auth check (backend={plan.backend}) — not yet implemented")


def _navigate_to_curriculum(plan: RunPlan) -> None:
    url = INSTRUCTOR_CURRICULUM_URL.format(course_id=plan.course_id)
    log(f"[stub] would navigate to {url}")
    # TODO(impl): mcp__Claude_in_Chrome__navigate(url) OR mcp__playwright__browser_navigate
    # TODO(impl): wait for [data-purpose="curriculum-list"] to be present
    # TODO(impl): if redirected to /join/login-popup/, abort with auth pointer


def _resolve_lecture_dom_nodes(plan: RunPlan) -> dict[str, dict]:
    """Return {lecture_number: {wrapper_ref, has_video, has_article}} from the DOM.

    Uses the flat-DOM enumeration from udemy-resource-uploader/playbook.md
    (sections + lectures are siblings under curriculum-list, NOT nested).
    """
    # TODO(impl): execute the enumeration JS via
    #   mcp__Claude_in_Chrome__javascript_tool / mcp__playwright__browser_evaluate.
    #   Selector reference (confirmed in resource-uploader/playbook.md):
    #     [data-purpose="curriculum-list"]        — outer container
    #     [data-purpose="section-editor"]         — section row
    #     [data-purpose="lecture-editor"]         — lecture row wrapper
    #     [data-purpose="item-object-index"]      — "Lecture N:" / "Section N:"
    #     [data-purpose="item-full-title"]        — lecture title text
    #     [data-purpose="video-icon"]             — present when lecture has Video  # TODO: verify selector
    #     [data-purpose="article-icon"]           — present when lecture has Article (CONFIRMED)
    log("[stub] would enumerate curriculum DOM and resolve lecture targets")
    return {}


def _upload_one(lec: LecturePlan, plan: RunPlan) -> str:
    """Upload one lecture's MP4. Returns one of: UPLOADED, SKIPPED, REPLACED, FAILED."""
    log(f"[stub] would upload Lecture {lec.number}: {lec.mp4_path}")

    # ---- Step (a) Idempotency check ----
    # TODO(impl): if has_video AND not plan.force_replace → return "SKIPPED"
    # TODO(impl): if has_article AND plan.force_replace → prompt user explicitly
    #   (replace-with-video preserves attached resources per resource-uploader/playbook.md
    #   line ~146 "Article main-content does NOT block a later Video upload")

    # ---- Step (b) Open the content panel ----
    # TODO(impl): click [data-purpose="lecture-add-content-btn"] on lec's wrapper

    # ---- Step (c) Pick Video ----
    # Two paths:
    #   bare stub → click [data-purpose="select-video"] (CONFIRMED — see
    #               udemy-resource-uploader/playbook.md "add-content panel" table)
    #   replace   → click [data-purpose="replace-with-video"] (CONFIRMED in the same
    #               playbook's "edit-content panel" table). May prompt a
    #               "Replace existing video?" modal — confirm only if --force-replace
    #               is set, otherwise abort.

    # ---- Step (d) Locate the file input ----
    # TODO: verify selector. Conjecture by analogy with the Resources uploader:
    #   resources used: [data-purpose="asset-uploader-input"] wrapper + hidden
    #                   <input type="file" name="asset">
    #   video likely:   [data-purpose="video-uploader-input"] wrapper + hidden
    #                   <input type="file" name="file">  # TODO: verify both
    #   Filter for accept including "video/*" or extensions like .mp4,.mov to
    #   disambiguate if multiple file inputs are present.

    # ---- Step (e) Attach the file ----
    # Backend selection mirrors udemy-resource-uploader/playbook.md "File upload"
    # section:
    #   - playwright: mcp__playwright__browser_file_upload with absolute path —
    #     uses CDP Page.handleFileChooser, bypasses OS picker.
    #   - chrome MCP: mcp__Claude_in_Chrome__file_upload is sandboxed off
    #     (verified failing in resource-uploader's first apply run, error
    #     code -32000 "Not allowed"). Fall back to:
    #       * JS-click the hidden input via mcp__Claude_in_Chrome__javascript_tool
    #         → user picks the file in the OS dialog, OR
    #       * Drag-drop from Finder onto the upload zone (Uppy widget; same
    #         pattern as resources).

    # ---- Step (f) Wait for upload + transcode ----
    # This is the BIG difference vs resource upload. Video has two phases:
    #   1. Upload — progress bar 0→100%, typically 5-60s on a fast link.
    #   2. Transcode — server-side, 30s-2min depending on length. The lecture
    #      row shows a "Processing" badge during transcode and the Save button
    #      is DISABLED.
    # Poll strategy:
    #   - Find Save button (TBD selector — guesses: [data-purpose="save-lecture"],
    #     [data-purpose="content-tab-save"], or a plain <button> with text
    #     "Save". # TODO: verify on first run.
    #   - Poll its `disabled` attribute every 2s until it goes false.
    #   - Hard timeout: plan.transcode_timeout_sec. On timeout: screenshot +
    #     abort. Do NOT click Save while disabled (no-op, confusing).

    # ---- Step (g) Save ----
    # TODO(impl): click Save. Wait for the panel to close and the lecture row
    #   to show the video-icon / duration label.

    # ---- Step (h) Verify ----
    # TODO(impl): re-enumerate the lecture row. Confirm video-icon present and
    #   duration label appears. If not after a short retry window, return "FAILED".

    return "STUB"


def _run_browser_flow(plan: RunPlan) -> dict[str, str]:
    """Drive the upload flow per lecture. Returns {lecture_number: status}."""
    _ensure_auth(plan)
    _navigate_to_curriculum(plan)
    dom = _resolve_lecture_dom_nodes(plan)  # noqa: F841 — TODO(impl) wire up

    if len(plan.lectures) > PAUSE_AND_CONFIRM_THRESHOLD:
        log(
            f"PAUSE: plan has {len(plan.lectures)} lectures (> "
            f"{PAUSE_AND_CONFIRM_THRESHOLD}). Sanity-check before proceeding. "
            "[stub: would prompt user here]"
        )

    status: dict[str, str] = {}
    for lec in plan.lectures:
        if not lec.mp4_exists:
            status[lec.number] = "FAILED (missing source)"
            continue
        if any("0 bytes" in w or "exceeds Udemy" in w or "corrupt" in w for w in lec.warnings):
            status[lec.number] = "FAILED (sanity check)"
            continue
        status[lec.number] = _upload_one(lec, plan)
    return status


def print_report(plan: RunPlan, status: dict[str, str]) -> None:
    log("")
    log("=== REPORT ===")
    total_bytes = 0
    for lec in plan.lectures:
        s = status.get(lec.number, "UNKNOWN")
        title_str = f' — "{lec.title}"' if lec.title else ""
        log(
            f"  Section {lec.section} / Lecture {lec.number}"
            f"{title_str} / {lec.mp4_path.name} → {s}"
        )
        if s.startswith(("UPLOADED", "REPLACED")):
            total_bytes += lec.size_bytes
    log("")
    log(f"Total bytes uploaded: {_fmt_size(total_bytes)}")
    log("")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    course_root: Path = args.course_root.expanduser().resolve()
    if not course_root.is_dir():
        abort(f"--course-root '{course_root}' is not a directory.")

    # Resolve MP4 dir against course root if relative
    mp4_dir: Path = args.mp4_dir
    if not mp4_dir.is_absolute():
        mp4_dir = (course_root / mp4_dir).resolve()
    else:
        mp4_dir = mp4_dir.expanduser().resolve()

    # Parse outline (optional — only used to enrich titles + resolve --section / --all)
    outline_path = course_root / "course-outline.md"
    course_outline = _parse_course_outline(outline_path)
    if (args.section is not None or args.all) and not course_outline:
        abort(
            f"--section / --all require '{outline_path}' to be parseable, "
            "but no sections were detected. Use --lectures instead."
        )

    targets = _resolve_target_lectures(args, course_outline)

    lecture_plans = [
        _build_lecture_plan(section=sec, lec_index=lec, title=title, mp4_dir_abs=mp4_dir)
        for (sec, lec, title) in targets
    ]

    plan = RunPlan(
        course_id=args.course_id,
        course_root=course_root,
        mp4_dir=mp4_dir,
        backend=args.backend,
        lectures=lecture_plans,
        force_replace=args.force_replace,
        transcode_timeout_sec=args.transcode_timeout,
        dry_run=args.dry_run,
    )

    print_plan(plan)

    missing = [lec for lec in plan.lectures if not lec.mp4_exists]
    fatal_warns = [
        lec for lec in plan.lectures
        if any("0 bytes" in w or "exceeds Udemy" in w or "corrupt" in w for w in lec.warnings)
    ]

    if plan.dry_run:
        log("Dry-run only — no browser opened. To apply: re-run without --dry-run.")
        return 0

    if missing:
        abort(
            f"{len(missing)} planned MP4(s) missing on disk. Fix or run "
            "`udemy-lecture-video-renderer` first."
        )
    if fatal_warns:
        abort(
            f"{len(fatal_warns)} planned MP4(s) failed sanity checks "
            "(empty / too big / corrupt). Fix and retry."
        )

    log("Proceeding to browser flow (STUB — not yet implemented).")
    status = _run_browser_flow(plan)
    print_report(plan, status)

    failed = [num for num, s in status.items() if s.startswith("FAILED") or s == "STUB"]
    if failed:
        log(f"{len(failed)} lecture(s) did not complete successfully: {', '.join(failed)}")
        return 2 if any(s == "STUB" for s in status.values()) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
