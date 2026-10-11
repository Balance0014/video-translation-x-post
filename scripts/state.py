#!/usr/bin/env python3
"""Initialize and update private task state outside the shareable skill."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "preferences.md": SKILL / "references" / "default-preferences.md",
    "ledger.md": SKILL / "references" / "ledger-template.md",
}


def default_state_dir() -> Path:
    override = os.environ.get("VIDEO_TRANSLATION_X_STATE_DIR")
    if override:
        return Path(override).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "state" / "video-translation-x-post"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "paths", "record"))
    parser.add_argument("--state-dir", type=Path, default=default_state_dir())
    parser.add_argument("--entry-file", type=Path, help="Markdown entry to append with record")
    args = parser.parse_args()
    state = args.state_dir.expanduser().resolve()
    if args.command in ("init", "record"):
        state.mkdir(parents=True, exist_ok=True)
        for name, source in TEMPLATES.items():
            destination = state / name
            if not destination.exists():
                shutil.copyfile(source, destination)
    if args.command == "record":
        if not args.entry_file or not args.entry_file.is_file():
            parser.error("record requires --entry-file pointing to a Markdown file")
        entry = args.entry_file.read_text(encoding="utf-8").strip()
        if not entry:
            parser.error("ledger entry is empty")
        with (state / "ledger.md").open("a", encoding="utf-8") as stream:
            stream.write("\n\n" + entry + "\n")
    for name in TEMPLATES:
        destination = state / name
        print(f"{name}: {destination} ({'exists' if destination.exists() else 'missing'})")


if __name__ == "__main__":
    main()
