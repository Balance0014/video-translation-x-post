#!/usr/bin/env python3
"""Check exported media streams, duration, aspect ratio, and full decode."""

from __future__ import annotations

import argparse
import filecmp
import re
import subprocess
from pathlib import Path

from media_tools import find_ffmpeg


def probe(ffmpeg: str, path: Path) -> tuple[float, str, bool]:
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True, timeout=20, check=False)
    info = result.stderr + result.stdout
    duration = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", info)
    video = next((line for line in info.splitlines() if "Video:" in line), "")
    if not duration or not video:
        raise ValueError(f"Missing duration or video stream in {path}")
    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
    return seconds, video.strip(), "Audio:" in info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--delivered", type=Path, help="Copied deliverable to compare byte for byte")
    parser.add_argument("--sample", action="store_true", help="Skip source-duration comparison")
    args = parser.parse_args()
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        parser.error("ffmpeg not on PATH")
    if not args.output.is_file():
        parser.error("Exported video does not exist")
    if args.speed <= 0:
        parser.error("Speed must be positive")
    duration, video, audio = probe(ffmpeg, args.output)
    if not audio:
        parser.error("Export has no audio stream")
    if "SAR 1:1" not in video:
        parser.error(f"Non-square pixel aspect ratio; check the export: {video}")
    if args.source and not args.sample:
        if not args.source.is_file():
            parser.error("Source video does not exist")
        original, _, _ = probe(ffmpeg, args.source)
        expected = original / args.speed
        if abs(duration - expected) > max(0.65, expected * 0.01):
            parser.error(f"Duration {duration:.2f}s differs from expected {expected:.2f}s")
    result = subprocess.run([ffmpeg, "-hide_banner", "-v", "error", "-i", str(args.output),
                             "-f", "null", "-"], capture_output=True, text=True,
                            timeout=600, check=False)
    if result.returncode:
        parser.error(f"Full decode failed: {result.stderr[-800:]}")
    if args.delivered:
        if not args.delivered.is_file() or not filecmp.cmp(args.output, args.delivered,
                                                           shallow=False):
            parser.error("Delivered copy differs from verified export")
    print(f"PASS: {duration:.2f}s; audio present; square pixels; full decode; {video}")
    if args.delivered:
        print("PASS: delivered copy matches byte for byte")


if __name__ == "__main__":
    main()
