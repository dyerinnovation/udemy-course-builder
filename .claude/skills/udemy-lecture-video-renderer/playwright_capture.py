#!/usr/bin/env python3
"""Capture per-click slide frames via Playwright against a running Slidev dev server.

This replaces the broken `slidev export --range N --with-clicks` path. The
Slidev RUNTIME handles clicks perfectly (that's why the live HTML preview
works) — only the CLI export is broken. So we drive the dev server directly
via headless Chromium, navigating `/<page>?clicks=<M>` for each click state
and snapshotting.

Output naming (consumed by mux.py):
    slide-NN-cM.png   NN = slide index in the lecture (1-indexed),
                      M = click state (0..N_clicks)

Prerequisites:
- Slidev dev server must be running for the target section. The skill
  expects `http://localhost:<port>` where port = 3030 + section_num * 10
  (matches the convention in slidev/package.json's dev:N scripts).
- python3 -m pip install playwright
- python3 -m playwright install chromium

Usage:
    python playwright_capture.py --lecture 2.1 \
        --course-root /path/to/course \
        --out-dir /tmp/lecture-2.1-assets
"""
from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent


def _expected_port(section_num: int) -> int:
    """Slidev dev port per the project convention (slidev/package.json):
    dev:1 → 3030, dev:2 → 3040, dev:3 → 3050, etc.
    """
    return 3020 + section_num * 10


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def capture_lecture_clicks(
    lecture_id: str,
    course_root: Path,
    out_dir: Path,
    script_click_counts: list[int],
    dev_server_url: str | None = None,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
) -> list[Path]:
    """Capture per-click PNG frames for all slides of a lecture.

    For each script SLIDE K (1-indexed within the lecture):
      - If script_click_counts[K-1] == 0: capture ONE final-state PNG → slide-KK-c0.png
      - If script_click_counts[K-1] > 0: validate slidev clicksTotal == script clicks,
        then capture (clicks+1) PNGs → slide-KK-c0.png ... slide-KK-cN.png

    Hard-aborts on:
    - Dev server not reachable
    - Slide-count mismatch (script SLIDEs vs slidev effective slides in lecture range)
    - Per-slide click-count mismatch on chunked slides
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "ERROR: playwright not installed. Run:\n"
            "  python3 -m pip install playwright\n"
            "  python3 -m playwright install chromium"
        )

    # Import find_lecture_page_range from slides_export (same skill dir)
    sys.path.insert(0, str(_SKILL_DIR))
    from slides_export import find_lecture_page_range

    section_num = int(lecture_id.split(".")[0])
    section_deck = course_root / "slidev" / f"section-{section_num}.md"
    if not section_deck.exists():
        raise FileNotFoundError(f"Slidev section deck not found: {section_deck}")

    # Determine dev server URL
    if dev_server_url is None:
        port = _expected_port(section_num)
        dev_server_url = f"http://localhost:{port}"
        if not _is_port_open("localhost", port):
            raise RuntimeError(
                f"Slidev dev server not reachable at {dev_server_url}. "
                f"Start it first:\n"
                f"  cd {course_root}/slidev && npm run dev:{section_num}\n"
                f"OR (if using Claude Preview MCP):\n"
                f"  preview_start with launch.json entry 'slidev-section-{section_num}'"
            )

    out_dir.mkdir(parents=True, exist_ok=True)

    # Compute lecture's slidev page range (effective slide numbering)
    first_page, last_page = find_lecture_page_range(section_deck, lecture_id)
    slide_count = last_page - first_page + 1

    if len(script_click_counts) != slide_count:
        raise ValueError(
            f"Slide-count mismatch for lecture {lecture_id}: "
            f"script has {len(script_click_counts)} SLIDE sections, "
            f"slidev has {slide_count} effective slides in pages {first_page}-{last_page}."
        )

    print(
        f"[capture] lecture {lecture_id}: slidev pages {first_page}-{last_page} "
        f"({slide_count} slides) via {dev_server_url}",
        file=sys.stderr,
    )
    print(
        f"[capture] script click counts: {script_click_counts}",
        file=sys.stderr,
    )

    written: list[Path] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=1,
            )
            page = context.new_page()

            # Warm-up: navigate to /1 so __slidev__ initializes
            page.goto(f"{dev_server_url}/1")
            page.wait_for_function(
                "() => { try { return !!(window.__slidev__ && window.__slidev__.nav); } catch (e) { return false; } }",
                timeout=15000,
            )

            for k_zero, slidev_page in enumerate(range(first_page, last_page + 1)):
                k = k_zero + 1
                script_clicks = script_click_counts[k_zero]

                # Query slidev's actual clicksTotal for this slide
                page.goto(f"{dev_server_url}/{slidev_page}")
                page.wait_for_function(
                    "(target) => { try { "
                    "  const n = window.__slidev__ && window.__slidev__.nav; "
                    "  if (!n) return false; "
                    "  const cur = (n.currentSlideNo && n.currentSlideNo.value !== undefined) "
                    "    ? n.currentSlideNo.value : n.currentSlideNo; "
                    "  return cur === target; "
                    "} catch (e) { return false; } }",
                    arg=slidev_page,
                    timeout=8000,
                )
                # Small settle to ensure components mount
                page.wait_for_timeout(400)
                slidev_clicks_total = page.evaluate(
                    "() => window.__slidev__.nav.clicksTotal?.value "
                    "?? window.__slidev__.nav.clicksTotal ?? 0"
                )

                # Decide which click states to capture
                if script_clicks == 0:
                    # Single final-state frame
                    states_to_capture = [slidev_clicks_total]
                    label = (
                        f"slide-{k:02d}-c0.png  (final state, slidev clicks={slidev_clicks_total})"
                    )
                else:
                    if slidev_clicks_total != script_clicks:
                        browser.close()
                        raise ValueError(
                            f"Click-count mismatch on slide {k} (slidev page {slidev_page}) "
                            f"of lecture {lecture_id}: script declares {script_clicks} "
                            f"[click] markers, but slidev runtime reports clicksTotal="
                            f"{slidev_clicks_total}. Reconcile by editing either the "
                            f"script's [click] count or the slidev component."
                        )
                    states_to_capture = list(range(slidev_clicks_total + 1))
                    label = (
                        f"slide-{k:02d}-c0..c{slidev_clicks_total}.png  "
                        f"({slidev_clicks_total + 1} click-states)"
                    )

                # Capture each click state
                for m_idx, click_state in enumerate(states_to_capture):
                    page.goto(f"{dev_server_url}/{slidev_page}?clicks={click_state}")
                    page.wait_for_function(
                        "(target) => { try { "
                        "  const n = window.__slidev__ && window.__slidev__.nav; "
                        "  if (!n) return false; "
                        "  const cur = (n.currentSlideNo && n.currentSlideNo.value !== undefined) "
                        "    ? n.currentSlideNo.value : n.currentSlideNo; "
                        "  return cur === target; "
                        "} catch (e) { return false; } }",
                        arg=slidev_page,
                        timeout=8000,
                    )
                    # Let animations settle
                    page.wait_for_timeout(450)
                    # Close any open goto/overview dialogs that may have popped up
                    page.evaluate(
                        "() => { for (const sel of ['#slidev-goto-dialog', '.slidev-overview']) "
                        "{ const d = document.querySelector(sel); if (d) d.style.display='none'; } }"
                    )
                    dst = out_dir / f"slide-{k:02d}-c{m_idx}.png"
                    page.screenshot(path=str(dst), full_page=False)
                    written.append(dst)

                print(f"[capture] {label}", file=sys.stderr)

        finally:
            browser.close()

    print(
        f"[capture] wrote {len(written)} per-click PNG(s) to {out_dir}",
        file=sys.stderr,
    )
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="playwright_capture.py",
        description="Capture per-click slide PNGs via Playwright against a running Slidev dev server.",
    )
    ap.add_argument("--lecture", required=True, help="Lecture ID, e.g. '2.1'")
    ap.add_argument("--course-root", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument(
        "--dev-server-url",
        default=None,
        help="Slidev dev server URL (default: auto-detect on port 3030+section*10)",
    )
    ap.add_argument(
        "--click-counts",
        default=None,
        help="Comma-separated per-slide [click] counts. If omitted, parsed from the lecture script.",
    )
    args = ap.parse_args(argv)

    if args.click_counts:
        script_click_counts = [int(x.strip()) for x in args.click_counts.split(",")]
    else:
        sys.path.insert(0, str(_SKILL_DIR))
        from parse_lecture import parse_lecture
        parsed = parse_lecture(args.lecture, args.course_root)
        script_click_counts = [s["click_count"] for s in parsed]

    try:
        written = capture_lecture_clicks(
            lecture_id=args.lecture,
            course_root=args.course_root,
            out_dir=args.out_dir,
            script_click_counts=script_click_counts,
            dev_server_url=args.dev_server_url,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"[capture] {len(written)} PNG(s) ready in {args.out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
