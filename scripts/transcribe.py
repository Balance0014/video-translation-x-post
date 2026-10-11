#!/usr/bin/env python3
"""Make a draft source-language SRT with faster-whisper; human review is required."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from media_tools import find_ffmpeg


def timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", default="en")
    parser.add_argument("--model", default="base.en",
                        help="faster-whisper model name or local model directory")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Input video does not exist")
    if args.output.exists() and not args.overwrite:
        parser.error("Output exists; pass --overwrite to replace it")
    if args.language != "en" and args.model.endswith(".en"):
        parser.error("Choose a multilingual model for non-English audio")
    try:
        from faster_whisper import WhisperModel
        import numpy as np
    except ImportError as error:
        parser.error(f"ASR dependency is unavailable: {error}. Install requirements.txt")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        parser.error("ffmpeg not on PATH; install FFmpeg before transcribing")
    decoded = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(args.input),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"],
        capture_output=True, check=False, timeout=1800,
    )
    if decoded.returncode or not decoded.stdout:
        parser.error(f"Audio decode failed: {decoded.stderr.decode(errors='replace')[-600:]}")
    audio = np.frombuffer(decoded.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    segments, _ = model.transcribe(audio, language=args.language,
                                   vad_filter=True, beam_size=5)
    cues = []
    for segment in segments:
        words = segment.text.strip().replace("\n", " ")
        if words:
            cues.append(f"{len(cues)+1}\n{timestamp(segment.start)} --> "
                        f"{timestamp(segment.end)}\n{words}")
    if not cues:
        parser.error("No speech was transcribed; check the source audio")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(cues) + "\n", encoding="utf-8")
    print(f"Draft transcript: {args.output} ({len(cues)} cues)")
    print("Review names, numbers, timestamps, and cut-off phrases before translation.")


if __name__ == "__main__":
    main()
