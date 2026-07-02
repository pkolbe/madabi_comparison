#!/usr/bin/env python3
"""Harmonize OpenAIRE harvest to the unified schema (single source)."""
import sys
from pathlib import Path

from harmonize_io import harmonize_file

CODE_DIR = Path(__file__).resolve().parent

_DEDUP_WARNING = (
    "Warning: This script does not deduplicate raw OpenAIRE records.\n"
    "Run dedupe_sources.py before harmonizing unless the raw file is already deduplicated."
)


def main() -> None:
    print(_DEDUP_WARNING, file=sys.stderr, flush=True)
    print("Harmonizing OpenAIRE only.", flush=True)
    summary = harmonize_file("openaire", CODE_DIR)
    print(f"Wrote {summary['rows']} rows to: {summary['output']}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"clean_openaire.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
