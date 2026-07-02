#!/usr/bin/env python3
"""
Deduplicate openaire.csv and openalex.csv in data/raw/.

Uses shared normalization from dedup.py. Does not modify madabi.
Report: data/processed/dedup_report.json
"""
import sys
from pathlib import Path

from dedup import DEDUP_SOURCES, run_deduplication

CODE_DIR = Path(__file__).resolve().parent
DEDUP_REPORT_PATH = CODE_DIR.parent / "data" / "processed" / "dedup_report.json"


def main() -> None:
    report = run_deduplication(CODE_DIR, report_path=DEDUP_REPORT_PATH)

    for source_key in DEDUP_SOURCES:
        summary = report["sources"][source_key]
        print(
            f"[{source_key}] {summary['input_rows']} -> {summary['output_rows']} rows "
            f"(removed {summary['removed_total']}: "
            f"doi={summary['removed_by_doi']}, title={summary['removed_by_title']})"
        )
        print(
            f"  without DOI: {summary['rows_without_doi']}, "
            f"without DOI/title: {summary['rows_without_doi_or_title']}"
        )

    print(f"\nWrote report: {DEDUP_REPORT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
