"""Command line: python -m patchdiff [--no-warnings] [--encoding NAME] old.csv new.csv"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .diff import diff_patches
from .model.patch_model import PatchError
from .parser import load_patch
from .report import render_diff


def _diff_patch_files(
    old_path: str | Path,
    new_path: str | Path,
    *,
    encoding: str | None = None,
    with_warnings: bool = True,
) -> str:
    """Compare two patch files and return the diff as plain text.

    The encoding applies to both files. If it is not given, each file is read as UTF-8,
    and in the local encoding of the machine if it is not valid UTF-8.
    """
    old_patch = load_patch(old_path, encoding=encoding)
    new_patch = load_patch(new_path, encoding=encoding)
    return render_diff(diff_patches(old_patch, new_patch), with_warnings=with_warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m patchdiff",
        description="Print a human readable diff of two patch CSV files, "
        "and warnings about rows and columns that look like a mistake.",
    )
    parser.add_argument("old", help="path to the original patch")
    parser.add_argument("new", help="path to the updated patch")
    parser.add_argument(
        "--no-warnings",
        action="store_true",
        help="print the differences only, with no warnings",
    )
    parser.add_argument(
        "--encoding",
        metavar="NAME",
        help="encoding of both files, for example cp1250. "
        "By default UTF-8 is tried first, then the local encoding of this machine",
    )
    args = parser.parse_args(argv)

    try:
        report = _diff_patch_files(args.old, args.new, encoding=args.encoding, with_warnings=not args.no_warnings)
    except PatchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        # Without the "[Errno 2]" prefix and the quotes that str(error) adds
        print(f"error: {error.strerror}: {error.filename}", file=sys.stderr)
        return 2

    # Values can be in any language. Do not depend on the console code page.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
