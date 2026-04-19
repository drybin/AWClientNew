#!/usr/bin/env python3
"""Fail if a Windows PE has no RT_GROUP_ICON resource (no embedded app icon).

Used in CI after PyInstaller so a missing icon= is caught immediately.
Requires: pip install pefile
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "exe",
        type=Path,
        help="Path to .exe (e.g. dist/aw-qt/aw-qt.exe)",
    )
    args = parser.parse_args()
    exe: Path = args.exe

    if not exe.is_file():
        print(f"ERROR: not a file: {exe}", file=sys.stderr)
        return 2

    try:
        import pefile
    except ImportError:
        print("ERROR: install pefile: pip install pefile", file=sys.stderr)
        return 2

    # RT_GROUP_ICON — directory of icon groups shown by Explorer
    RT_GROUP_ICON = pefile.RESOURCE_TYPE["RT_GROUP_ICON"]

    # Full parse so IMAGE_DIRECTORY_ENTRY_RESOURCE is loaded (fast_load skips resources).
    pe = pefile.PE(str(exe))

    if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        print(f"ERROR: no resource section in {exe}", file=sys.stderr)
        return 1

    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.id == RT_GROUP_ICON:
            print(f"OK: {exe} has RT_GROUP_ICON (embedded icon resource)")
            return 0

    print(
        f"ERROR: {exe} has no RT_GROUP_ICON — PyInstaller did not embed an icon "
        f"(check aw.spec exe_icon= and aw-qt/media/logo/logo.ico)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
