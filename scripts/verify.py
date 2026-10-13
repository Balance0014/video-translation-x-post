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


def read_srt(path: Path) -> list[tuple[int, int, str]]:
    """Read checked cue times in milliseconds and reject broken subtitle structure."""
    value = path.read_text(encoding="utf-8-sig").strip()
    if not value:
        raise ValueError(f"Subtitle file is empty: {path}")
    stamp = r"(\d+):([0-5]\d):([0-5]\d),(\d{3})"
    pattern = re.compile(rf"{stamp}\s+-->\s+{stamp}")
    cues: list[tuple[int, int, str]] = []
    for index, block in enumerate(re.split(r"\n\s*\n", value), start=1):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError(f"Invalid SRT cue {index} in {path}")
        match = pattern.fullmatch(lines[1].strip())
        if not match:
            raise ValueError(f"Invalid timing in SRT cue {index} in {path}")
        numbers = list(map(int, match.groups()))
        start = ((numbers[0] * 60 + numbers[1]) * 60 + numbers[2]) * 1000 + numbers[3]
        end = ((numbers[4] * 60 + numbers[5]) * 60 + numbers[6]) * 1000 + numbers[7]
        content = "\n".join(lines[2:]).strip()
        if not content or end <= start:
            raise ValueError(f"Empty or nonpositive SRT cue {index} in {path}")
        if cues and start < cues[-1][1]:
            raise ValueError(f"Overlapping SRT cue {index} in {path}")
        cues.append((start, end, content))
    return cues


def check_retimed_cues(source: list[tuple[int, int, str]],
                       delivered: list[tuple[int, int, str]], speed: float,
                       tolerance_ms: int = 50) -> None:
    """Confirm every exported cue follows the source SRT after speeding up."""
    expected = [(round(start / speed), round(end / speed), content)
                for start, end, content in source
                if round(end / speed) > round(start / speed)]
    if len(expected) != len(delivered):
        raise ValueError(f"Retimed SRT has {len(delivered)} cues; expected {len(expected)}")
    for index, (original, actual) in enumerate(zip(expected, delivered), start=1):
        if (abs(original[0] - actual[0]) > tolerance_ms
                or abs(original[1] - actual[1]) > tolerance_ms):
            raise ValueError(f"Retimed SRT cue {index} differs from source/speed by more "
                             f"than {tolerance_ms} ms")
        if original[2] != actual[2]:
            raise ValueError(f"Retimed SRT cue {index} text differs from source subtitles")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--subtitles", type=Path,
                        help="Editable SRT; defaults to a same-named sidecar when present")
    parser.add_argument("--source-subtitles", type=Path,
                        help="Source-timeline Chinese SRT; compare every delivered cue after speed change")
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
    if args.source_subtitles and args.sample:
        parser.error("--source-subtitles checks full exports, not samples")
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
    subtitles = args.subtitles or args.output.with_suffix(".srt")
    if args.subtitles and not subtitles.is_file():
        parser.error("Editable SRT does not exist")
    if args.source_subtitles and not args.source_subtitles.is_file():
        parser.error("Source-timeline Chinese SRT does not exist")
    if args.source_subtitles and not subtitles.is_file():
        parser.error("Editable final SRT is required with --source-subtitles")
    try:
        cues = read_srt(subtitles) if subtitles.is_file() and subtitles.stat().st_size else []
        if args.source_subtitles:
            check_retimed_cues(read_srt(args.source_subtitles), cues, args.speed)
    except ValueError as error:
        parser.error(str(error))
    if cues:
        last = cues[-1][1] / 1000
        if last > duration + 0.65:
            parser.error(f"SRT extends to {last:.2f}s beyond video duration {duration:.2f}s")
        print(f"PASS: editable SRT ends at {last:.2f}s")
    if args.source_subtitles:
        print(f"PASS: all {len(cues)} retimed subtitle cues match the source timeline")
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
