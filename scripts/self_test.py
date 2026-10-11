#!/usr/bin/env python3
"""Exercise state, rendering, and verification in a temporary workspace."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from media_tools import find_ffmpeg


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(list(args), check=True, timeout=120)


def main() -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise SystemExit("ffmpeg is missing from PATH")
    with tempfile.TemporaryDirectory(prefix="video-translation-x-selftest-") as temp_name:
        temp = Path(temp_name)
        run(sys.executable, str(ROOT / "scripts/state.py"), "init",
            "--state-dir", str(temp / "state"))
        source = temp / "source.mp4"
        run(ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-y", str(source))
        zh = temp / "zh.srt"
        en = temp / "en.srt"
        zh.write_text("1\n00:00:00,200 --> 00:00:03,500\n这是一段中文测试。\n", encoding="utf-8")
        en.write_text("1\n00:00:00,200 --> 00:00:03,500\nEnglish test caption.\n", encoding="utf-8")
        for layout in ("bilingual", "chinese-only"):
            output = temp / f"{layout}.mp4"
            command = [sys.executable, str(ROOT / "scripts/render.py"),
                       "--input", str(source), "--subtitles", str(zh),
                       "--output", str(output), "--layout", layout,
                       "--watermark", "翻译：@example", "--speed", "1.2",
                       "--title", "Test|Video"]
            if layout == "bilingual":
                command += ["--english-subtitles", str(en)]
            else:
                command += ["--mirror", "--mirror-verified"]
            run(*command)
            run(sys.executable, str(ROOT / "scripts/verify.py"),
                "--output", str(output), "--source", str(source), "--speed", "1.2")
    print("PASS: private state, both subtitle layouts, speed, mirror gate, audio, and decode")


if __name__ == "__main__":
    main()
