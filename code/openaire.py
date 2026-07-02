#!/usr/bin/env python3
"""Harvest Mannheim datasets from the OpenAIRE Graph API."""

import csv
from pathlib import Path

import requests

from config import load_config

CODE_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = CODE_DIR.parent / "data" / "raw" / "openaire.csv"

ORG_SEARCH_URL = "https://api.openaire.eu/graph/v1/organizations"
RP_SEARCH_URL = "https://api.openaire.eu/graph/v2/researchProducts"


def get_org_id_from_ror(ror_id: str, page_size: int = 1) -> str:
    """Resolve the OpenAIRE organization ID for a ROR URL."""
    params = {"pid": ror_id, "pageSize": page_size}
    resp = requests.get(ORG_SEARCH_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"No organization found for ROR {ror_id}.")

    org = results[0]
    org_id = org.get("id")
    legal_name = org.get("legalName", "(unnamed)")
    print(f"Found organization: {legal_name} (id={org_id})")

    if not org_id:
        raise RuntimeError("Organization found but response contained no 'id'.")
    return org_id


def extract_doi(product: dict) -> str:
    """Extract a DOI from OpenAIRE product PIDs or instance alternate identifiers."""
    if not isinstance(product, dict):
        return ""

    pids = product.get("pids") or []
    for pid in pids:
        if not isinstance(pid, dict):
            continue
        if pid.get("scheme", "").lower() == "doi":
            return pid.get("value", "")

    instances = product.get("instances") or []
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        for alt in inst.get("alternateIdentifiers") or []:
            if not isinstance(alt, dict):
                continue
            if alt.get("scheme", "").lower() == "doi":
                return alt.get("value", "")

    return ""


def extract_title(product: dict) -> str:
    return product.get("mainTitle", "")


def extract_publisher(product: dict) -> str:
    if not isinstance(product, dict):
        return ""
    return product.get("publisher", "") or ""


def extract_authors(product: dict) -> str:
    authors = product.get("authors") or []
    names = [a.get("fullName") for a in authors if isinstance(a, dict) and a.get("fullName")]
    return "; ".join(names)


def fetch_datasets_for_org(org_id: str, *, page_size: int = 100, max_pages: int = 1000) -> list:
    """Fetch dataset research products linked to the given organization."""
    all_items = []
    params = {
        "type": "dataset",
        "relOrganizationId": org_id,
        "pageSize": page_size,
        "cursor": "*",
    }

    for _ in range(max_pages):
        resp = requests.get(RP_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        header = data.get("header", {})
        results = data.get("results", [])
        print(f"Page {header.get('page')}: {len(results)} datasets")

        for rp in results:
            all_items.append(
                {
                    "DOI": extract_doi(rp),
                    "Title": extract_title(rp),
                    "Creators": extract_authors(rp),
                    "Publisher": extract_publisher(rp),
                }
            )

        next_cursor = header.get("nextCursor")
        if not next_cursor:
            break
        params["cursor"] = next_cursor

    return all_items


def write_csv(rows: list, filename: Path) -> None:
    fieldnames = ["DOI", "Title", "Creators", "Publisher"]
    filename.parent.mkdir(parents=True, exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Wrote CSV: {filename} ({len(rows)} rows)")


def filter_dataset_level_dois(rows: list) -> list:
    """
    Exclude file-level DOIs (three slashes in the DOI path).

    OpenAIRE may return DOIs for individual files inside a deposit. This
    comparison operates at the dataset/deposit level, so those file-level
    entries are removed intentionally; the parent deposit record is kept.
    """
    return [
        row
        for row in rows
        if not (row.get("DOI") and str(row["DOI"]).count("/") == 3)
    ]


if __name__ == "__main__":
    cfg = load_config()
    institution = cfg.get("institution", {})
    openaire_cfg = cfg.get("openaire", {})

    ror_id = institution.get("ror_id")
    if not ror_id:
        raise RuntimeError("institution.ror_id is not set in code/config.yaml")

    org_id = get_org_id_from_ror(ror_id)
    datasets = fetch_datasets_for_org(
        org_id,
        page_size=int(openaire_cfg.get("page_size", 100)),
        max_pages=int(openaire_cfg.get("max_pages", 1000)),
    )
    datasets = filter_dataset_level_dois(datasets)
    write_csv(datasets, OUTPUT_CSV)
