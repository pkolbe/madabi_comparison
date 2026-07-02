#!/usr/bin/env python3
"""
Optional pipeline runner for the madabi comparison workflow.

Does not overwrite raw API harvest files unless --harvest is passed.
"""
import argparse
import subprocess
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent


def run_script(name: str) -> None:
    path = CODE_DIR / name
    if not path.is_file():
        raise SystemExit(f"Pipeline script not found: {path}")
    print(f"\n>>> Running {name}")
    result = subprocess.run([sys.executable, str(path)], cwd=str(CODE_DIR))
    if result.returncode != 0:
        raise SystemExit(
            f"{name} failed with exit code {result.returncode}. "
            f"Run from the repository root with: python code/run_pipeline.py "
            f"or cd code && python run_pipeline.py"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run madabi comparison pipeline")
    parser.add_argument(
        "--harvest",
        action="store_true",
        help="Re-fetch OpenAIRE and OpenAlex metadata (overwrites data/raw/*.csv)",
    )
    parser.add_argument(
        "--skip-dedupe",
        action="store_true",
        help="Skip deduplication of openaire/openalex (dedupe_sources.py)",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Skip harmonization of all sources (clean_all.py; run dedupe_sources.py first)",
    )
    parser.add_argument(
        "--skip-compare",
        action="store_true",
        help="Skip compare_sources.py",
    )
    parser.add_argument(
        "--skip-analyze",
        action="store_true",
        help="Skip analyze_comparison.py",
    )
    args = parser.parse_args()

    if args.harvest:
        run_script("openaire.py")
        run_script("openalex.py")

    if not args.skip_dedupe:
        run_script("dedupe_sources.py")

    if not args.skip_clean:
        run_script("clean_all.py")

    if not args.skip_compare:
        run_script("compare_sources.py")

    if not args.skip_analyze:
        run_script("analyze_comparison.py")

    print("\nPipeline finished.")


if __name__ == "__main__":
    main()
