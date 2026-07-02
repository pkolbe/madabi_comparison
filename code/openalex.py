#!/usr/bin/env python3
"""Harvest Mannheim datasets from the OpenAlex API."""

import csv
import os
import time
from pathlib import Path

import requests

from config import load_config
from normalize import normalize_doi

CODE_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = CODE_DIR.parent / "data" / "raw" / "openalex.csv"
BASE_URL = "https://api.openalex.org/works"


def extract_authors(work: dict) -> str:
    authors = []
    for auth in work.get("authorships", []):
        author_info = auth.get("author") or {}
        name = author_info.get("display_name")
        if name:
            authors.append(name)
    return "; ".join(authors)


def extract_primary_location_display_name(work: dict) -> str:
    if not isinstance(work, dict):
        return ""

    primary_location = work.get("primary_location")
    if not isinstance(primary_location, dict):
        return ""

    source = primary_location.get("source")
    if isinstance(source, dict):
        name = source.get("display_name")
        if name:
            return name

    raw_name = primary_location.get("raw_source_name")
    return raw_name or ""


def fetch_works_for_institution(
    ror_id: str,
    *,
    mailto: str | None,
    per_page: int = 200,
    sleep_seconds: float = 0.2,
):
    """Yield dataset works affiliated with the institution identified by ROR."""
    cursor = "*"
    filter_param = f"authorships.institutions.ror:{ror_id},type:dataset"

    while True:
        params: dict = {
            "filter": filter_param,
            "per-page": per_page,
            "cursor": cursor,
        }
        if mailto:
            params["mailto"] = mailto

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            break

        for work in results:
            yield work

        meta = data.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break

        time.sleep(sleep_seconds)


def main() -> None:
    cfg = load_config()
    institution = cfg.get("institution", {})
    openalex_cfg = cfg.get("openalex", {})

    ror_id = institution.get("ror_id")
    if not ror_id:
        raise RuntimeError("institution.ror_id is not set in code/config.yaml")

    mailto = os.environ.get("OPENALEX_MAILTO", "").strip() or None
    if not mailto:
        print(
            "Warning: OPENALEX_MAILTO is not set. "
            "OpenAlex recommends setting a contact email for polite pool access.",
            flush=True,
        )

    fieldnames = ["DOI", "Title", "Creators", "Publisher"]
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_CSV, mode="w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        count = 0
        for work in fetch_works_for_institution(
            ror_id,
            mailto=mailto,
            per_page=int(openalex_cfg.get("per_page", 200)),
            sleep_seconds=float(openalex_cfg.get("rate_limit_sleep_seconds", 0.2)),
        ):
            writer.writerow(
                {
                    "DOI": normalize_doi(work.get("doi", "")),
                    "Title": work.get("title", ""),
                    "Creators": extract_authors(work),
                    "Publisher": extract_primary_location_display_name(work),
                }
            )
            count += 1

    print(f"Finished. Wrote {count} records to '{OUTPUT_CSV}'.")


if __name__ == "__main__":
    main()
