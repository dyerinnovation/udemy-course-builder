#!/usr/bin/env python3
"""Mux per-slide PNG + MP3 pairs into a final lecture MP4.

For each paired slide-NN.png + slide-NN.mp3 in the assets directory:
  1. Encode a segment MP4 (PNG held for audio duration, letterboxed to 1920x1080)
  2. Write concat-list.txt
  3. Concatenate all segments into the final output MP4

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

    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", str(png_path),
        "-i", str(mp3_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
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

    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
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


def mux(
    assets_dir: Path,
    output: Path,
    force: bool = False,
) -> Path:
    """Run the full mux pipeline for assets in assets_dir.

    Returns the path to the final output MP4.
    """
    # Discover paired slide-NN.png + slide-NN.mp3 files
    png_files = sorted(assets_dir.glob("slide-*.png"))
    if not png_files:
        raise FileNotFoundError(
            f"No slide-NN.png files found in {assets_dir}. "
            "Run slides_export.py first."
        )

    # Validate pairs
    pairs: list[tuple[Path, Path]] = []
    for png in png_files:
        mp3 = png.with_suffix(".mp3")
        if not mp3.exists():
            raise FileNotFoundError(
                f"Audio file missing for {png.name}: expected {mp3}. "
                "Run tts_render.py first."
            )
        pairs.append((png, mp3))

    print(
        f"[mux] {len(pairs)} slide pair(s) found in {assets_dir}",
        file=sys.stderr,
    )

    # Encode segments
    output.parent.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []

    for png, mp3 in pairs:
        # Extract slide number from filename (slide-NN.png → NN)
        slide_num = int(png.stem.replace("slide-", ""))
        seg_path = assets_dir / f"segment-{slide_num:02d}.mp4"
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
