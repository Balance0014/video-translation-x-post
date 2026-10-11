"""Small shared helpers for the skill's CLI scripts."""

from __future__ import annotations

import shutil
from pathlib import Path


def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for path in (Path.home() / ".local/bin/ffmpeg",
                 Path.home() / ".local/bin/ffmpeg.exe",
                 Path("/opt/homebrew/bin/ffmpeg")):
        if path.is_file():
            return str(path)
    return None
