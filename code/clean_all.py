#!/usr/bin/env python3
"""Harmonize MADABI, OpenAIRE, and OpenAlex to the unified schema.

Does not deduplicate raw files. Run dedupe_sources.py first for OpenAIRE and OpenAlex.
"""
import csv
import sys
from pathlib import Path

from constants import SCHEMA_COLUMNS
from harmonize_io import harmonize_file, validate_schema_columns

CODE_DIR = Path(__file__).resolve().parent
DEDUP_REPORT_PATH = CODE_DIR.parent / "data" / "processed" / "dedup_report.json"
HARMONIZE_SOURCES = ("madabi", "openaire", "openalex")


def main() -> None:
    print(
        "Harmonizing all sources (MADABI, OpenAIRE, OpenAlex).\n"
        "Note: This script does not deduplicate. Run dedupe_sources.py first "
        "for OpenAIRE and OpenAlex raw CSVs.",
        flush=True,
    )
    if not DEDUP_REPORT_PATH.is_file():
        print(
            f"Warning: {DEDUP_REPORT_PATH} not found. "
            "OpenAIRE/OpenAlex raw files may still contain duplicates. "
            "Run: python dedupe_sources.py",
            file=sys.stderr,
            flush=True,
        )

    summaries = []
    for key in HARMONIZE_SOURCES:
        summaries.append(harmonize_file(key, CODE_DIR))
        print(f"[harmonize {key}] {summaries[-1]['rows']} rows -> {summaries[-1]['output']}")

    for summary in summaries:
        with open(summary["output"], newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            validate_schema_columns(list(reader.fieldnames or []))

    print(f"\nAll outputs validated ({', '.join(SCHEMA_COLUMNS)}).")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"clean_all.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
