#!/usr/bin/env python3
"""Copy the canonical ppt_quality.py into every Lambda package that imports it.

DeckBuilder, ExportPpt (ppt_merger) and the infographic generator each have a
CodeUri that is their own folder, so a module that lives at the CG-Backend root
is not on the Lambda path. Run this before `sam build` (deploy.ps1 does it).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "ppt_quality.py"
DEST_DIRS = [
    ROOT / "lambda" / "deck_builder",
    ROOT / "lambda" / "ppt_merger",
    ROOT / "lambda" / "strands_infographic_generator",
]


def sync() -> list[Path]:
    if not SRC.is_file():
        raise SystemExit(f"missing canonical module: {SRC}")
    written: list[Path] = []
    for dest_dir in DEST_DIRS:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "ppt_quality.py"
        shutil.copyfile(SRC, dest)
        written.append(dest)
    return written


if __name__ == "__main__":
    for path in sync():
        print(f"synced {path}")
    sys.exit(0)
