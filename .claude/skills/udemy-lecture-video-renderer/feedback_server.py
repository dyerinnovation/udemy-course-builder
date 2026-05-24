#!/usr/bin/env python3
"""Small stdlib HTTP server for the per-lecture feedback workflow.

Replaces `python -m http.server` for the `feedback-preview` launch config.
Adds three things on top of plain static-file serving:

  1. `POST /api/save-bundle` — accepts the JSON bundle the feedback HTML's
     "Export bundle" button produces, writes it to
     `<course_root>/feedback/<date>/<lecture>-feedback-bundle-<ts>.json`,
     and then invokes `unpack_feedback.unpack()` in-process to produce the
     round-N markdown + extracted images. Returns 200 JSON describing the
     written files, or 400 on validation/parse error.

  2. `GET /lectures/<rest>` — bridge route that serves files from a
     configurable `--lecture-output-root` (default
     `/Volumes/Dev_SSD/Dyer_Innovation_Lecture_Videos/Udemy/Claude-Architect-Course/lectures`).
     This lets the feedback HTML render slide thumbnails from the SSD
     location without the assets having to live under `--directory`. Returns
     404 for a missing file, 503 if the configured root volume isn't mounted,
     and rejects any path traversal that escapes the configured root.

  3. Everything else falls through to `SimpleHTTPRequestHandler` against
     `--directory` — so URLs like `/feedback/lecture-2.2/index.html` and
     `/artifacts/lectures/.lecture-2.1-assets/slide-01-c0.png` still work
     for backwards compatibility / non-migrated courses.

CORS is permissive (`Access-Control-Allow-Origin: *`) and `OPTIONS`
preflights are answered with 204. The server is stdlib-only — no flask,
no werkzeug — so it stays portable across whichever Python the user
points at it.

Usage:
    python feedback_server.py \\
      --port 8767 \\
      --directory <course_root> \\
      --lecture-output-root /Volumes/Dev_SSD/.../lectures
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import mimetypes
import os
import socketserver
import sys
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

# Imported lazily inside the handler so an import error in unpack_feedback
# turns into a clean 500 JSON response instead of crashing the server.
_UNPACK_IMPORT_ERROR: Exception | None = None
try:
    import unpack_feedback  # type: ignore
except Exception as _exc:  # pragma: no cover — surfaced at request time
    unpack_feedback = None  # type: ignore[assignment]
    _UNPACK_IMPORT_ERROR = _exc


# ---------------------------------------------------------------------------
# Config (set by main(), read by the handler)
# ---------------------------------------------------------------------------

class _Config:
    """Per-server config. Populated once in main() and read by the handler."""

    course_root: Path = Path.cwd()
    lecture_output_root: Path = Path(
        "/Volumes/Dev_SSD/Dyer_Innovation_Lecture_Videos/Udemy/"
        "Claude-Architect-Course/lectures"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_timestamp() -> str:
    """Filesystem-friendly ISO timestamp (no colons / dots)."""
    return _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")


def _today_iso() -> str:
    return _dt.date.today().isoformat()


def _safe_resolve(root: Path, rel: str) -> Path | None:
    """Resolve `rel` against `root`, refusing any traversal that escapes.

    Returns the resolved Path on success, or None if the request tried to
    escape (`..`) or otherwise resolved outside the root tree.
    """
    # Strip any leading slashes — they're rooted at the bridge prefix, not /
    rel = rel.lstrip("/")
    # urllib percent-decodes for us via SimpleHTTPRequestHandler; do it again
    # defensively in case a caller hand-builds a path.
    rel = urllib.parse.unquote(rel)
    if not rel:
        return None
    # No absolute paths — caller's `rel` must stay relative.
    if Path(rel).is_absolute():
        return None
    try:
        candidate = (root / rel).resolve(strict=False)
        root_resolved = root.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    # candidate must be root_resolved itself OR a descendant of it.
    if candidate != root_resolved and root_resolved not in candidate.parents:
        return None
    return candidate


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class FeedbackRequestHandler(SimpleHTTPRequestHandler):
    """Extends SimpleHTTPRequestHandler with the POST endpoint + /lectures bridge."""

    # ---- common helpers ----------------------------------------------------

    def _write_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def end_headers(self) -> None:  # noqa: D401 — SimpleHTTPRequestHandler override
        # Make sure CORS headers reach every response (including static files).
        # Guard against double-write: only add if the underlying connection
        # hasn't already had them via _write_json.
        # SimpleHTTPRequestHandler calls end_headers() in its own send_head().
        # We re-emit unconditionally — duplicates are harmless for CORS.
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    # ---- routing -----------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802 — http stdlib convention
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/save-bundle":
            self._handle_save_bundle()
            return
        self._write_json(404, {"ok": False, "error": f"unknown POST path: {parsed.path}"})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._write_json(200, {
                "ok": True,
                "course_root": str(_Config.course_root),
                "lecture_output_root": str(_Config.lecture_output_root),
                "lecture_output_root_mounted": _Config.lecture_output_root.exists(),
            })
            return
        if path.startswith("/lectures/") or path == "/lectures":
            self._handle_lectures_bridge(path, head_only=False)
            return
        # Fall through to SimpleHTTPRequestHandler's static serving (uses
        # `directory` from the server / handler init).
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            # 200 with empty body — health is GET-only semantically, but
            # return a clean status here too.
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            return
        if path.startswith("/lectures/") or path == "/lectures":
            self._handle_lectures_bridge(path, head_only=True)
            return
        super().do_HEAD()

    # ---- POST /api/save-bundle --------------------------------------------

    def _handle_save_bundle(self) -> None:
        if unpack_feedback is None:
            self._write_json(500, {
                "ok": False,
                "error": (
                    "unpack_feedback module failed to import on server start: "
                    f"{_UNPACK_IMPORT_ERROR!r}"
                ),
            })
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(400, {"ok": False, "error": "invalid Content-Length"})
            return
        if length <= 0:
            self._write_json(400, {"ok": False, "error": "empty request body"})
            return
        # Cap at 256MB to avoid runaway memory on a malformed request.
        if length > 256 * 1024 * 1024:
            self._write_json(400, {"ok": False, "error": "request body too large"})
            return

        try:
            raw_body = self.rfile.read(length)
        except (OSError, ConnectionError) as exc:
            self._write_json(400, {"ok": False, "error": f"failed to read body: {exc}"})
            return

        try:
            bundle = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._write_json(400, {"ok": False, "error": f"invalid JSON: {exc}"})
            return

        if not isinstance(bundle, dict):
            self._write_json(400, {"ok": False, "error": "bundle must be a JSON object"})
            return

        lecture = bundle.get("lecture")
        slides = bundle.get("slides")
        if not isinstance(lecture, str) or not lecture.strip():
            self._write_json(400, {"ok": False, "error": "missing/invalid 'lecture' field"})
            return
        if not isinstance(slides, list):
            self._write_json(400, {"ok": False, "error": "missing/invalid 'slides' field"})
            return

        # Date dir derived from exported_at (if present + parseable), else today.
        exported_at = bundle.get("exported_at") or ""
        if isinstance(exported_at, str) and "T" in exported_at:
            date_str = exported_at.split("T", 1)[0]
        else:
            date_str = _today_iso()

        course_root = _Config.course_root
        date_dir = course_root / "feedback" / date_str
        try:
            date_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._write_json(500, {"ok": False, "error": f"mkdir failed: {exc}"})
            return

        ts = _iso_timestamp()
        bundle_path = date_dir / f"{lecture}-feedback-bundle-{ts}.json"
        try:
            bundle_path.write_bytes(raw_body)
        except OSError as exc:
            self._write_json(500, {"ok": False, "error": f"write bundle failed: {exc}"})
            return

        try:
            md_path, image_paths = unpack_feedback.unpack(
                bundle_path=bundle_path,
                course_root=course_root,
                date_override=date_str,
            )
        except Exception as exc:  # broad on purpose — surface unpacker errors as 400
            self._write_json(400, {
                "ok": False,
                "error": f"unpack_feedback failed: {exc}",
                "bundle_path": str(bundle_path),
            })
            return

        # Build relative paths (relative to course_root) for the client to
        # surface to the user in the toast.
        def _rel(p: Path) -> str:
            try:
                return str(p.relative_to(course_root))
            except ValueError:
                return str(p)

        self._write_json(200, {
            "ok": True,
            "bundle_path": str(bundle_path),
            "bundle_relative": _rel(bundle_path),
            "markdown_path": str(md_path),
            "markdown_relative": _rel(md_path),
            "image_count": len(image_paths),
        })

    # ---- GET /lectures/... -------------------------------------------------

    def _handle_lectures_bridge(self, path: str, *, head_only: bool = False) -> None:
        rel = path[len("/lectures"):]  # leading slash retained intentionally
        if rel == "" or rel == "/":
            self._write_json(404, {"ok": False, "error": "no file specified"})
            return

        root = _Config.lecture_output_root
        if not root.exists():
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(
                    (
                        f"503 Service Unavailable: lecture-output-root not reachable: {root}\n"
                        "Check that the external SSD is mounted, or pass "
                        "--lecture-output-root <local-path>.\n"
                    ).encode("utf-8")
                )
            return

        target = _safe_resolve(root, rel)
        if target is None:
            self._write_json(400, {"ok": False, "error": "invalid path (traversal blocked)"})
            return
        if not target.exists() or not target.is_file():
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(f"404 Not Found: {rel}\n".encode("utf-8"))
            return

        ctype, _ = mimetypes.guess_type(target.name)
        if ctype is None:
            ctype = "application/octet-stream"
        try:
            stat = target.stat()
        except OSError as exc:
            self._write_json(500, {"ok": False, "error": f"stat failed: {exc}"})
            return

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header(
            "Last-Modified", self.date_time_string(int(stat.st_mtime))
        )
        self._send_cors_headers()
        self.end_headers()
        if head_only:
            return
        try:
            with target.open("rb") as fh:
                # SimpleHTTPRequestHandler uses copyfile under the hood.
                self.copyfile(fh, self.wfile)  # type: ignore[arg-type]
        except (BrokenPipeError, ConnectionResetError):
            # Client went away mid-transfer — common with browser previews.
            return

    # ---- logging -----------------------------------------------------------

    def log_message(self, fmt: str, *args) -> None:  # noqa: D401, A003
        # Quieter default — match http.server but route through stderr.
        sys.stderr.write(
            f"[{self.log_date_time_string()}] {self.address_string()} - {fmt % args}\n"
        )


class _ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="feedback_server.py",
        description=(
            "Small HTTP server for the per-lecture feedback workflow. "
            "Serves static files (like python -m http.server), plus a "
            "POST /api/save-bundle endpoint and a /lectures/<rest> bridge "
            "route into the external lecture-output-root."
        ),
    )
    ap.add_argument(
        "--port", type=int, default=8767,
        help="TCP port to bind (default: 8767)",
    )
    ap.add_argument(
        "--directory", type=Path, default=Path("."),
        help="Course root / static document root (default: current dir)",
    )
    ap.add_argument(
        "--lecture-output-root",
        type=Path,
        default=Path(
            "/Volumes/Dev_SSD/Dyer_Innovation_Lecture_Videos/Udemy/"
            "Claude-Architect-Course/lectures"
        ),
        help=(
            "Root for /lectures/<rest> bridge serving "
            "(default: external SSD claude-architect-course lectures dir)"
        ),
    )
    ap.add_argument(
        "--bind", default="127.0.0.1",
        help="Address to bind (default: 127.0.0.1 — loopback only)",
    )
    args = ap.parse_args(argv)

    course_root = args.directory.resolve()
    if not course_root.is_dir():
        print(f"ERROR: --directory not a directory: {course_root}", file=sys.stderr)
        return 1

    _Config.course_root = course_root
    _Config.lecture_output_root = args.lecture_output_root

    # Bake `directory=` into the handler class so SimpleHTTPRequestHandler
    # serves static files from `course_root`.
    handler_cls = type(
        "BoundFeedbackHandler",
        (FeedbackRequestHandler,),
        {"directory": str(course_root)},
    )
    # SimpleHTTPRequestHandler reads `directory` from the constructor in
    # Python 3.7+. Wrap it so we don't have to touch SimpleHTTPRequestHandler.__init__.
    def _factory(*a, **kw):
        return handler_cls(*a, directory=str(course_root), **kw)

    server = _ThreadingServer((args.bind, args.port), _factory)
    bind_display = args.bind if args.bind != "0.0.0.0" else "all interfaces"  # noqa: S104
    mounted = "yes" if args.lecture_output_root.exists() else "NO (will return 503)"

    print("=" * 72, file=sys.stderr)
    print("feedback_server.py — lecture-feedback workflow", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print(f"  listening on:        http://{bind_display}:{args.port}", file=sys.stderr)
    print(f"  course_root:         {course_root}", file=sys.stderr)
    print(f"  lecture_output_root: {args.lecture_output_root}", file=sys.stderr)
    print(f"  ssd mounted:         {mounted}", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Endpoints:", file=sys.stderr)
    print("    GET  /<anything>            → static file from course_root", file=sys.stderr)
    print("    GET  /lectures/<rest>       → file from lecture_output_root", file=sys.stderr)
    print("    GET  /api/health            → JSON status", file=sys.stderr)
    print("    POST /api/save-bundle       → save + unpack feedback JSON bundle", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Smoke test (in another shell):", file=sys.stderr)
    print(
        f"    curl -s http://127.0.0.1:{args.port}/api/health | python3 -m json.tool",
        file=sys.stderr,
    )
    print(
        f"    curl -s -X POST http://127.0.0.1:{args.port}/api/save-bundle \\\n"
        "      -H 'Content-Type: application/json' \\\n"
        "      -d '{\"lecture\":\"2.99\",\"slides\":[]}'",
        file=sys.stderr,
    )
    print("=" * 72, file=sys.stderr)
    print("Press Ctrl-C to stop.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
