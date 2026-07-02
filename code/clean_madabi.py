#!/usr/bin/env python3
"""Harmonize Mannheim MADABI metadata to the unified schema (single source)."""
import sys
from pathlib import Path

from harmonize_io import harmonize_file

CODE_DIR = Path(__file__).resolve().parent


def main() -> None:
    print("Harmonizing MADABI only.", flush=True)
    summary = harmonize_file("madabi", CODE_DIR)
    print(f"Wrote {summary['rows']} rows to: {summary['output']}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"clean_madabi.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
