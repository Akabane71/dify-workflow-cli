#!/usr/bin/env python3
"""Compatibility entrypoint for editable installs and legacy build commands.

Recommended modern build command:
    uv run python -m build

Legacy-compatible alternatives:
    python setup.py bdist_wheel
    python setup.py sdist
"""

try:
    from setuptools import setup
except ModuleNotFoundError as exc:
    raise SystemExit(
        "setuptools is required for legacy setup.py commands.\n"
        "Recommended: uv run python build_package.py\n"
        "Alternative: uv run python -m build\n"
        "Legacy: python -m pip install setuptools wheel && python setup.py bdist_wheel"
    ) from exc


if __name__ == "__main__":
    setup()