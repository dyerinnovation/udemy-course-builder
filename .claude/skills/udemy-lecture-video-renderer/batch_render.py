#!/usr/bin/env python3
"""Batch-render a list of lectures sequentially.

Wraps render.py so a whole section (or a custom lecture list) can render
unattended. For each lecture:

  1. Wipe its assets directory (mitigates the --force orphan-asset bug:
     if chunk counts shrank since a prior render, stale per-click PNGs/MP3s
     would otherwise be picked up by mux.py and produce a broken MP4).
  2. Invoke render.py for that lecture.
  3. Capture exit code, wall-clock duration, final MP4 size.
  4. Continue on failure — don't halt the batch. Failures are reported at
     the end so a single bad lecture doesn't block the rest.

After all renders, prints a per-lecture summary table and exits 0 if all
passed, 1 otherwise.

Usage:
    # Render all lectures in a section (auto-discovered from scripts/)
    python batch_render.py --section 2 --course-root /path/to/course

    # Render an explicit list
    python batch_render.py --lectures 2.2,2.3,2.4 --course-root .

    # Render an explicit list, skipping ones whose MP4 already exists
    python batch_render.py --section 2 --course-root . --skip-existing

    # Pass --force through to render.py for every lecture
    python batch_render.py --section 2 --course-root . --force-each
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent
_RENDER_PY = _SKILL_DIR / "render.py"

# Same lecture-ID glob as parse_lecture.find_lecture_file
_LECTURE_FILE_RE = re.compile(r"^(\d+)\.(\d+)-.*\.md$")


def discover_lectures_in_section(course_root: Path, section_num: int) -> list[str]:
    """Find all X.Y lecture IDs in scripts/section-NN-*/ for a section, sorted by Y."""
    scripts_dir = course_root / "scripts"
    section_dirs = list(scripts_dir.glob(f"section-{section_num:02d}-*")) + \
                   list(scripts_dir.glob(f"section-{section_num}-*"))
    section_dirs = [d for d in section_dirs if d.is_dir()]
    if not section_dirs:
        raise FileNotFoundError(
            f"No section directory found for section {section_num} under {scripts_dir}"
        )
    if len(section_dirs) > 1:
        raise RuntimeError(
            f"Multiple section directories match section {section_num}: "
            + ", ".join(str(d) for d in section_dirs)
        )
    section_dir = section_dirs[0]

    lecture_ids: list[tuple[int, int, str]] = []
    for f in section_dir.iterdir():
        if not f.is_file() or not f.name.endswith(".md"):
            continue
        m = _LECTURE_FILE_RE.match(f.name)
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            if major == section_num:
                lecture_ids.append((major, minor, f"{major}.{minor}"))
    lecture_ids.sort()  # sorts by (major, minor)
    return [lid for _, _, lid in lecture_ids]


def _wipe_assets(course_root: Path, lecture_id: str) -> None:
    """Delete the lecture's per-asset directory if it exists."""
    assets_dir = course_root / "artifacts" / "lectures" / f".lecture-{lecture_id}-assets"
    if assets_dir.exists():
        shutil.rmtree(assets_dir)


def _mp4_path(course_root: Path, lecture_id: str) -> Path:
    return course_root / "artifacts" / "lectures" / f"lecture-{lecture_id}.mp4"


def render_one(
    lecture_id: str,
    course_root: Path,
    wipe_assets: bool,
    force: bool,
    python_bin: str,
) -> dict:
    """Render one lecture. Returns a result dict."""
    out_mp4 = _mp4_path(course_root, lecture_id)
    if wipe_assets:
        _wipe_assets(course_root, lecture_id)

    cmd = [
        python_bin, str(_RENDER_PY),
        "--lecture", lecture_id,
        "--course-root", str(course_root),
        "--out", str(out_mp4),
    ]
    if force:
        cmd.append("--force")

    print(f"\n========== Rendering lecture {lecture_id} ==========", file=sys.stderr)
    print("  " + " ".join(cmd), file=sys.stderr)
    t0 = time.monotonic()
    try:
        result = subprocess.run(cmd, check=False)
        rc = result.returncode
    except KeyboardInterrupt:
        # Re-raise so the batch loop exits cleanly
        raise
    except Exception as exc:  # noqa: BLE001
        return {
            "lecture": lecture_id,
            "ok": False,
            "rc": -1,
            "duration_s": time.monotonic() - t0,
            "size_mb": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    dur = time.monotonic() - t0

    size_mb = out_mp4.stat().st_size / (1024 * 1024) if out_mp4.exists() else 0.0
    return {
        "lecture": lecture_id,
        "ok": rc == 0 and out_mp4.exists(),
        "rc": rc,
        "duration_s": dur,
        "size_mb": size_mb,
        "error": None if rc == 0 else f"render.py exited {rc}",
    }


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 70, file=sys.stderr)
    print(" BATCH RENDER SUMMARY", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    header = f" {'LECTURE':<8}  {'RESULT':<8}  {'DURATION':>10}  {'SIZE':>8}  NOTES"
    print(header, file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    total_dur = 0.0
    total_size = 0.0
    n_ok = n_fail = 0
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        if r["ok"]:
            n_ok += 1
        else:
            n_fail += 1
        dur_str = f"{r['duration_s']:.1f}s"
        size_str = f"{r['size_mb']:.1f}MB" if r["size_mb"] > 0 else "-"
        notes = "" if r["ok"] else (r.get("error") or "")
        print(
            f" {r['lecture']:<8}  {mark:<8}  {dur_str:>10}  {size_str:>8}  {notes}",
            file=sys.stderr,
        )
        total_dur += r["duration_s"]
        total_size += r["size_mb"]
    print("-" * 70, file=sys.stderr)
    print(
        f" Totals: {n_ok} passed, {n_fail} failed | "
        f"wall={total_dur/60:.1f} min | size={total_size:.1f} MB",
        file=sys.stderr,
    )
    print("=" * 70 + "\n", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="batch_render.py",
        description="Render multiple lectures sequentially.",
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--section", type=int,
        help="Render all lectures discovered in scripts/section-NN-*/",
    )
    group.add_argument(
        "--lectures", type=str,
        help="Comma-separated list of lecture IDs to render (e.g. '2.2,2.3,2.4')",
    )

    ap.add_argument(
        "--course-root", required=True, type=Path,
        help="Course repo root",
    )
    ap.add_argument(
        "--skip-existing", action="store_true",
        help="Skip lectures whose lecture-X.Y.mp4 already exists",
    )
    ap.add_argument(
        "--wipe-assets", action="store_true",
        help="Wipe each lecture's assets dir before render (nuclear option). "
             "Rarely needed — render.py now auto-prunes orphan per-click "
             "assets at the start of each run. Use only if you want to "
             "re-render every asset from scratch (slowest path, full TTS "
             "+ Playwright cost).",
    )
    ap.add_argument(
        "--force-each", action="store_true",
        help="Pass --force through to render.py for every lecture "
             "(full re-render ignoring cached assets)",
    )
    # Default to /usr/bin/python3 if it exists — that's the canonical
    # pipeline python on macOS (has elevenlabs, dotenv, playwright, httpx).
    # Falling back to sys.executable means batch_render won't auto-pick
    # up Xcode's bundled python (which lacks renderer deps) when invoked
    # by tools that don't preserve PATH.
    _DEFAULT_PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
    ap.add_argument(
        "--python", default=_DEFAULT_PYTHON,
        help="Python interpreter to use for each render.py invocation. "
             f"Defaults to {_DEFAULT_PYTHON!r}.",
    )

    args = ap.parse_args(argv)
    course_root = args.course_root.resolve()

    if args.section is not None:
        try:
            lecture_ids = discover_lectures_in_section(course_root, args.section)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not lecture_ids:
            print(f"ERROR: no lectures discovered for section {args.section}", file=sys.stderr)
            return 1
    else:
        lecture_ids = [s.strip() for s in args.lectures.split(",") if s.strip()]

    if args.skip_existing:
        before = list(lecture_ids)
        lecture_ids = [lid for lid in lecture_ids if not _mp4_path(course_root, lid).exists()]
        skipped = [lid for lid in before if lid not in lecture_ids]
        if skipped:
            print(f"[batch] skipping {len(skipped)} existing: {', '.join(skipped)}",
                  file=sys.stderr)

    if not lecture_ids:
        print("[batch] no lectures to render", file=sys.stderr)
        return 0

    print(
        f"[batch] rendering {len(lecture_ids)} lecture(s): {', '.join(lecture_ids)}",
        file=sys.stderr,
    )

    results: list[dict] = []
    try:
        for lid in lecture_ids:
            res = render_one(
                lecture_id=lid,
                course_root=course_root,
                wipe_assets=args.wipe_assets,
                force=args.force_each,
                python_bin=args.python,
            )
            results.append(res)
    except KeyboardInterrupt:
        print("\n[batch] interrupted by user. Partial summary follows.", file=sys.stderr)

    print_summary(results)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
