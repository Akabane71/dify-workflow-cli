#!/usr/bin/env python3
"""One-shot package builder for local distribution artifacts.

Usage:
    python build_package.py

The script prefers `uv run python -m build` when `uv` is available, and
falls back to `python -m build` otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _build_command() -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "python", "-m", "build"]
    return [sys.executable, "-m", "build"]


def main() -> None:
    root = Path(__file__).resolve().parent
    dist_dir = root / "dist"

    command = _build_command()
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=root, check=True)

    wheels = sorted(dist_dir.glob("*.whl"), key=lambda path: path.stat().st_mtime)
    if not wheels:
        raise SystemExit("Build finished but no wheel was found in dist/.")

    wheel = wheels[-1]
    print(f"\nBuilt wheel: {wheel}")
    print(f"Install with: {sys.executable} -m pip install \"{wheel}\"")


if __name__ == "__main__":
    main()