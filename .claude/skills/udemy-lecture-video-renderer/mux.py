#!/usr/bin/env python3
"""Mux per-click PNG + MP3 pairs into a final lecture MP4.

For each paired slide-NN-cM.png + slide-NN-cM.mp3 in the assets directory:
  1. Encode a segment MP4 (PNG held for audio duration, letterboxed to 1920x1080)
  2. Write concat-list.txt in (slide, click) order
  3. Concatenate all segments into the final output MP4

File-naming contract (produced by slides_export.py + tts_render.py):
    slide-NN-cM.png   NN = slide index, M = click state (0..N_clicks)
    slide-NN-cM.mp3   corresponding narration sub-chunk

Concat order: slide-01-c0, slide-02-c0, slide-02-c1, ..., slide-03-c0, ...
(within each slide, click states play in order; then advance to next slide)

Usage:
    python mux.py --assets-dir /tmp/lecture-2.1-assets --output lecture-2.1.mp4
    python mux.py --assets-dir /tmp/lecture-2.1-assets --output lecture-2.1.mp4 --force
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# ffmpeg invocations (locked)
# ---------------------------------------------------------------------------

_SEGMENT_VFILTER = (
    "scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
)


def _probe_duration(media_path: Path) -> float:
    """Return the duration (seconds) of an audio or video file via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed on {media_path.name}: {result.stderr.strip()}"
        )
    return float(result.stdout.strip())


def encode_segment(
    png_path: Path,
    mp3_path: Path,
    out_path: Path,
    force: bool = False,
) -> None:
    """Encode one slide PNG + audio MP3 into a segment MP4.

    Skips if out_path is newer than both inputs and force is not set.
    """
    if (
        not force
        and out_path.exists()
        and out_path.stat().st_size > 0
        and out_path.stat().st_mtime > max(
            png_path.stat().st_mtime,
            mp3_path.stat().st_mtime,
        )
    ):
        print(f"[mux] {out_path.name}  skipped (cached)", file=sys.stderr)
        return

    print(f"[mux] encoding {out_path.name} ...", file=sys.stderr, end="", flush=True)

    # Probe the audio duration so we can pass it as -t explicitly.
    # NOTE on -shortest vs -t: -shortest is unreliable with -loop 1 looped
    # images — for reasons that are not fully nailed down (likely related to
    # encoder lookahead/buffering on long clips), it leaves 1-3s of silent
    # video tail at the end of longer segments (clips >8s seem to be hit;
    # short bullet slides escape it). Setting -t to the exact MP3 duration
    # eliminates the gap entirely (within ±40ms). We keep -r 25 -g 25 so the
    # video stream has 1s keyframe spacing — clean concat boundaries when
    # mux.py runs the concat demuxer over the segments. See playbook.md
    # "Per-segment silent-tail bug" for the full diagnosis.
    audio_dur = _probe_duration(mp3_path)

    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", str(png_path),
        "-i", str(mp3_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        "-g", "25",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{audio_dur:.3f}",
        "-vf", _SEGMENT_VFILTER,
        "-y",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nffmpeg stderr:\n{result.stderr}", file=sys.stderr)
        raise RuntimeError(
            f"ffmpeg segment encoding failed for {out_path.name} "
            f"(exit code {result.returncode})"
        )

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f" done ({size_mb:.1f} MB)", file=sys.stderr)


def concat_segments(segment_paths: list[Path], output: Path, force: bool = False) -> None:
    """Concatenate segment MP4s into a final output MP4 via ffmpeg concat demuxer."""
    if not segment_paths:
        raise ValueError("No segments provided for concatenation.")

    concat_list = output.parent / "concat-list.txt"
    concat_list.write_text(
        "\n".join(f"file '{seg.resolve()}'" for seg in segment_paths),
        encoding="utf-8",
    )

    print(
        f"[mux] concat {len(segment_paths)} segments → {output.name} ...",
        file=sys.stderr,
        end="",
        flush=True,
    )

    # NOTE on -c copy vs re-encode: the original "stream-copy" concat is
    # fast (seconds) but fragile — combined with x264 b-frames + per-segment
    # PTS rebasing it can produce timestamps that ffmpeg writes successfully
    # but QuickTime refuses to render (black frame + no audio). The fully
    # re-encoded concat takes ~15-30s for a 5-min lecture but produces a
    # clean, universally-playable MP4 with consistent frame rate, no PTS
    # drift, and no b-frame ordering quirks. The cost is acceptable: 5 min
    # of compute per lecture * 94 lectures = ~8 hours one-time, vs days of
    # "why doesn't this play?" debugging when uploaded to Udemy. We add
    # +faststart to put the moov atom up front so the MP4 is streamable
    # (Udemy + browsers seek faster). See playbook.md "Concat re-encode
    # rationale" for the full writeup.
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        "-g", "25",
        "-bf", "0",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-y",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nffmpeg stderr:\n{result.stderr}", file=sys.stderr)
        raise RuntimeError(
            f"ffmpeg concat failed (exit code {result.returncode})"
        )

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f" done ({size_mb:.1f} MB)", file=sys.stderr)


_NAME_RE = __import__("re").compile(r"^slide-(\d+)-c(\d+)$")


def _parse_slide_click(stem: str) -> tuple[int, int]:
    """Parse 'slide-NN-cM' → (NN, M). Raises ValueError on malformed name."""
    m = _NAME_RE.match(stem)
    if not m:
        raise ValueError(f"Unexpected filename stem: {stem!r} (expected 'slide-NN-cM')")
    return int(m.group(1)), int(m.group(2))


def mux(
    assets_dir: Path,
    output: Path,
    force: bool = False,
) -> Path:
    """Run the full mux pipeline for assets in assets_dir.

    Returns the path to the final output MP4.
    """
    # Discover paired slide-NN-cM.png + slide-NN-cM.mp3 files
    png_files = sorted(assets_dir.glob("slide-*-c*.png"))
    if not png_files:
        raise FileNotFoundError(
            f"No slide-NN-cM.png files found in {assets_dir}. "
            "Run slides_export.py first."
        )

    # Build ordered pairs sorted by (slide_idx, click_idx)
    pairs: list[tuple[int, int, Path, Path]] = []
    for png in png_files:
        slide_n, click_m = _parse_slide_click(png.stem)
        mp3 = png.with_suffix(".mp3")
        if not mp3.exists():
            raise FileNotFoundError(
                f"Audio file missing for {png.name}: expected {mp3.name}. "
                "Run tts_render.py first."
            )
        pairs.append((slide_n, click_m, png, mp3))

    pairs.sort(key=lambda x: (x[0], x[1]))

    print(
        f"[mux] {len(pairs)} per-click pair(s) found in {assets_dir}",
        file=sys.stderr,
    )

    # Encode segments
    output.parent.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []

    for slide_n, click_m, png, mp3 in pairs:
        seg_path = assets_dir / f"segment-{slide_n:02d}-c{click_m}.mp4"
        encode_segment(png, mp3, seg_path, force=force)
        segment_paths.append(seg_path)

    # Concatenate
    concat_segments(segment_paths, output, force=force)

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="mux.py",
        description="Mux per-slide PNG + MP3 pairs into a final lecture MP4.",
    )
    ap.add_argument(
        "--assets-dir",
        required=True,
        type=Path,
        help="Directory containing paired slide-NN.png + slide-NN.mp3 files",
    )
    ap.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for the final lecture .mp4",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-encode all segments, ignoring cache",
    )
    args = ap.parse_args(argv)

    try:
        out = mux(
            assets_dir=args.assets_dir,
            output=args.output,
            force=args.force,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"[mux] DONE: {out} ({size_mb:.1f} MB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
