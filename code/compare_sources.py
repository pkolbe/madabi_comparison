#!/usr/bin/env python3
"""
Cross-source comparison for madabi, OpenAIRE, and OpenAlex.

Matching priority per pair: DOI > exact title > normalized title.
Core overlap metrics use DOI matches only; title-based matches are reported
separately with explicit confidence labels.
"""
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from constants import DUPLICATE_KEYS_REPORT_PATH
from harmonize_io import load_harmonized_csv
from matching import (
    build_match_index,
    find_best_match,
    is_high_confidence_match,
    match_confidence_label,
    record_identity_key,
    summarize_duplicate_keys,
)

CODE_DIR = Path(__file__).resolve().parent
DATA_PROCESSED = CODE_DIR.parent / "data" / "processed"

FILE_MADABI = DATA_PROCESSED / "unified_mannheim_metadata_cleaned.csv"
FILE_OPENAIRE = DATA_PROCESSED / "openaire_cleaned.csv"
FILE_OPENALEX = DATA_PROCESSED / "openalex_cleaned.csv"

OUT_SUMMARY_JSON = DATA_PROCESSED / "comparison_summary.json"
OUT_SUMMARY_CSV = DATA_PROCESSED / "comparison_summary.csv"
OUT_MADABI_UPDATED = DATA_PROCESSED / "unified_mannheim_metadata_cleaned_with_overlap.csv"
OUT_MADABI_EXCLUSIVE = DATA_PROCESSED / "madabi_exclusive.csv"
OUT_OPENAIRE_EXCLUSIVE = DATA_PROCESSED / "openaire_exclusive.csv"
OUT_OPENALEX_EXCLUSIVE = DATA_PROCESSED / "openalex_exclusive.csv"
OUT_OPEN_EXCLUSIVE = DATA_PROCESSED / "openaire_openalex_exclusive.csv"
OUT_OPENAIRE_STRICT_EXCLUSIVE = DATA_PROCESSED / "openaire_strict_exclusive.csv"
OUT_OPENALEX_STRICT_EXCLUSIVE = DATA_PROCESSED / "openalex_strict_exclusive.csv"
OUT_OVERLAP_OPENAIRE = DATA_PROCESSED / "openaire_madabi_overlap.csv"
OUT_OVERLAP_OPENALEX = DATA_PROCESSED / "openalex_madabi_overlap.csv"

EXCLUSIVE_FIELDS = [
    "source",
    "doi",
    "title",
    "creators",
    "repository",
    "match_status",
]


def load_all_sources() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    madabi = load_harmonized_csv(str(FILE_MADABI), source_label="madabi")
    openaire = load_harmonized_csv(str(FILE_OPENAIRE), source_label="openaire")
    openalex = load_harmonized_csv(str(FILE_OPENALEX), source_label="openalex")
    return madabi, openaire, openalex


def match_details(
    record: Dict[str, Any],
    index: Dict[str, Any],
) -> Tuple[bool, bool, str, str]:
    """
    Return (any_match, doi_match, method, confidence) for a record against an index.
    """
    method, _ = find_best_match(record, index)
    if not method:
        return False, False, "none", ""
    return (
        True,
        is_high_confidence_match(method),
        method,
        match_confidence_label(method),
    )


def unique_record_count(records: List[Dict[str, Any]]) -> int:
    return len({record_identity_key(r) for r in records})


def pairwise_overlap_count(
    left: List[Dict[str, Any]],
    right_index: Dict[str, Any],
    *,
    doi_only: bool = False,
) -> int:
    matched_keys: Set[str] = set()
    for rec in left:
        any_match, doi_match, _, _ = match_details(rec, right_index)
        if doi_only and not doi_match:
            continue
        if not doi_only and not any_match:
            continue
        matched_keys.add(record_identity_key(rec))
    return len(matched_keys)


def strict_exclusive_records(
    records: List[Dict[str, Any]],
    other_indexes: List[Dict[str, Any]],
    *,
    doi_only: bool = False,
) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    result = []
    for rec in records:
        if any(
            (match_details(rec, idx)[1] if doi_only else match_details(rec, idx)[0])
            for idx in other_indexes
        ):
            continue
        key = record_identity_key(rec)
        if key in seen:
            continue
        seen.add(key)
        result.append(rec)
    return result


def symmetric_pairwise_overlap(
    left: List[Dict[str, Any]],
    right: List[Dict[str, Any]],
    left_index: Dict[str, Any],
    right_index: Dict[str, Any],
    *,
    doi_only: bool = False,
) -> int:
    keys: Set[str] = set()

    def add_overlap_key(rec: Dict[str, Any], other_index: Dict[str, Any]) -> None:
        any_match, doi_match, _, _ = match_details(rec, other_index)
        if doi_only and not doi_match:
            return
        if not doi_only and not any_match:
            return
        _, matched_rec = find_best_match(rec, other_index)
        doi = rec.get("doi_normalized", "") or (matched_rec or {}).get("doi_normalized", "")
        if doi:
            keys.add(f"doi:{doi}")
            return
        title = rec.get("title_normalized", "") or (matched_rec or {}).get(
            "title_normalized", ""
        )
        if title:
            keys.add(f"title:{title}")

    for rec in left:
        add_overlap_key(rec, right_index)
    for rec in right:
        add_overlap_key(rec, left_index)
    return len(keys)


def exclusive_records(
    records: List[Dict[str, Any]],
    other_index: Dict[str, Any],
    *,
    doi_only: bool = False,
) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    result = []
    for rec in records:
        any_match, doi_match, _, _ = match_details(rec, other_index)
        matched = doi_match if doi_only else any_match
        if matched:
            continue
        key = record_identity_key(rec)
        if key in seen:
            continue
        seen.add(key)
        result.append(rec)
    return result


def record_to_exclusive_row(rec: Dict[str, Any], status: str = "exclusive") -> Dict[str, str]:
    return {
        "source": rec.get("source", ""),
        "doi": rec.get("doi_normalized") or rec.get("doi", ""),
        "title": rec.get("title", ""),
        "creators": rec.get("creators", ""),
        "repository": rec.get("repository") or rec.get("repository_normalized", ""),
        "match_status": status,
    }


def write_exclusive_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXCLUSIVE_FIELDS)
        writer.writeheader()
        for rec in records:
            writer.writerow(record_to_exclusive_row(rec))


def merge_open_exclusive(
    openaire_ex: List[Dict[str, Any]],
    openalex_ex: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for rec in openaire_ex + openalex_ex:
        key = record_identity_key(rec)
        if key not in merged:
            merged[key] = rec
            continue
        existing = merged[key]
        sources = {existing.get("source", ""), rec.get("source", "")}
        existing["source"] = "+".join(sorted(s for s in sources if s))
    return list(merged.values())


def build_summary(
    madabi: List[Dict],
    openaire: List[Dict],
    openalex: List[Dict],
    openaire_index: Dict,
    openalex_index: Dict,
    madabi_ex: List[Dict],
    openaire_ex: List[Dict],
    openalex_ex: List[Dict],
    openaire_strict: List[Dict],
    openalex_strict: List[Dict],
) -> Dict[str, Any]:
    madabi_oa_doi = pairwise_overlap_count(madabi, openaire_index, doi_only=True)
    madabi_ox_doi = pairwise_overlap_count(madabi, openalex_index, doi_only=True)
    madabi_oa_any = pairwise_overlap_count(madabi, openaire_index, doi_only=False)
    madabi_ox_any = pairwise_overlap_count(madabi, openalex_index, doi_only=False)
    openaire_openalex_doi = symmetric_pairwise_overlap(
        openaire, openalex, openaire_index, openalex_index, doi_only=True
    )
    openaire_openalex_any = symmetric_pairwise_overlap(
        openaire, openalex, openaire_index, openalex_index, doi_only=False
    )

    three_way_doi: Set[str] = set()
    three_way_any: Set[str] = set()
    for rec in madabi:
        _, oa_doi, _, _ = match_details(rec, openaire_index)
        _, ox_doi, _, _ = match_details(rec, openalex_index)
        oa_any, _, _, _ = match_details(rec, openaire_index)
        ox_any, _, _, _ = match_details(rec, openalex_index)
        if oa_doi and ox_doi:
            three_way_doi.add(record_identity_key(rec))
        if oa_any and ox_any:
            three_way_any.add(record_identity_key(rec))

    return {
        "totals": {
            "madabi_rows": len(madabi),
            "madabi_unique": unique_record_count(madabi),
            "openaire_rows": len(openaire),
            "openaire_unique": unique_record_count(openaire),
            "openalex_rows": len(openalex),
            "openalex_unique": unique_record_count(openalex),
        },
        "pairwise_overlap_doi": {
            "madabi_openaire": madabi_oa_doi,
            "madabi_openalex": madabi_ox_doi,
            "openaire_openalex": openaire_openalex_doi,
        },
        "pairwise_overlap_any_method": {
            "madabi_openaire": madabi_oa_any,
            "madabi_openalex": madabi_ox_any,
            "openaire_openalex": openaire_openalex_any,
        },
        "three_way_overlap_doi": len(three_way_doi),
        "three_way_overlap_any_method": len(three_way_any),
        "exclusive_unique": {
            "madabi": len(madabi_ex),
            "openaire": len(openaire_ex),
            "openalex": len(openalex_ex),
            "openaire_or_openalex_not_madabi": len(
                merge_open_exclusive(openaire_ex, openalex_ex)
            ),
        },
        "exclusive_strict_unique": {
            "madabi": len(madabi_ex),
            "openaire": len(openaire_strict),
            "openalex": len(openalex_strict),
        },
    }


def summary_to_csv_rows(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    rows = []
    for section, values in summary.items():
        if isinstance(values, dict):
            for key, value in values.items():
                rows.append({"section": section, "metric": key, "value": str(value)})
        else:
            rows.append({"section": "root", "metric": section, "value": str(values)})
    return rows


def write_madabi_with_overlap(
    madabi_raw_rows: List[Dict[str, str]],
    fieldnames: List[str],
    madabi_records: List[Dict[str, Any]],
    openaire_index: Dict[str, Any],
    openalex_index: Dict[str, Any],
) -> None:
    extra_cols = [
        "overlap openaire",
        "overlap openalex",
        "overlap_openaire_doi",
        "overlap_openalex_doi",
        "match_method_openaire",
        "match_confidence_openaire",
        "match_method_openalex",
        "match_confidence_openalex",
    ]
    out_fields = list(fieldnames)
    for col in extra_cols:
        if col not in out_fields:
            out_fields.append(col)

    with open(OUT_MADABI_UPDATED, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for raw_row, rec in zip(madabi_raw_rows, madabi_records):
            oa_any, oa_doi, oa_method, oa_conf = match_details(rec, openaire_index)
            ox_any, ox_doi, ox_method, ox_conf = match_details(rec, openalex_index)
            row = dict(raw_row)
            row["overlap openaire"] = "1" if oa_any else "0"
            row["overlap openalex"] = "1" if ox_any else "0"
            row["overlap_openaire_doi"] = "1" if oa_doi else "0"
            row["overlap_openalex_doi"] = "1" if ox_doi else "0"
            row["match_method_openaire"] = oa_method if oa_any else ""
            row["match_confidence_openaire"] = oa_conf
            row["match_method_openalex"] = ox_method if ox_any else ""
            row["match_confidence_openalex"] = ox_conf
            writer.writerow(row)


def write_legacy_overlap_exports(
    madabi: List[Dict],
    openaire_index: Dict,
    openalex_index: Dict,
) -> Tuple[int, int]:
    out_fields = ["doi", "title", "creators", "repository"]
    written_oa = 0
    written_ox = 0

    with open(OUT_OVERLAP_OPENAIRE, "w", newline="", encoding="utf-8") as f_oa:
        writer = csv.DictWriter(f_oa, fieldnames=out_fields)
        writer.writeheader()
        seen: Set[str] = set()
        for rec in madabi:
            doi = rec.get("doi_normalized", "")
            if not doi or doi in seen:
                continue
            if doi in openaire_index["by_doi"]:
                matched = openaire_index["by_doi"][doi]
                writer.writerow(
                    {
                        "doi": doi,
                        "title": matched.get("title", ""),
                        "creators": matched.get("creators", ""),
                        "repository": matched.get("repository", ""),
                    }
                )
                seen.add(doi)
                written_oa += 1

    with open(OUT_OVERLAP_OPENALEX, "w", newline="", encoding="utf-8") as f_ox:
        writer = csv.DictWriter(f_ox, fieldnames=out_fields)
        writer.writeheader()
        seen = set()
        for rec in madabi:
            doi = rec.get("doi_normalized", "")
            if not doi or doi in seen:
                continue
            if doi in openalex_index["by_doi"]:
                matched = openalex_index["by_doi"][doi]
                writer.writerow(
                    {
                        "doi": doi,
                        "title": matched.get("title", ""),
                        "creators": matched.get("creators", ""),
                        "repository": matched.get("repository", ""),
                    }
                )
                seen.add(doi)
                written_ox += 1

    return written_oa, written_ox


def read_madabi_raw_rows() -> Tuple[List[Dict[str, str]], List[str]]:
    with open(FILE_MADABI, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def write_duplicate_keys_report(indexes: Dict[str, Dict[str, Any]]) -> None:
    report = summarize_duplicate_keys(indexes)
    DUPLICATE_KEYS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DUPLICATE_KEYS_REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    total = report.get("total_duplicate_rows", 0)
    if total:
        print(
            f"Warning: {total} duplicate index keys detected. "
            f"See {DUPLICATE_KEYS_REPORT_PATH}"
        )
    else:
        print(f"Wrote duplicate keys report: {DUPLICATE_KEYS_REPORT_PATH}")


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    madabi_raw_rows, madabi_fieldnames = read_madabi_raw_rows()
    madabi, openaire, openalex = load_all_sources()

    madabi_index = build_match_index(madabi, source_label="madabi")
    openaire_index = build_match_index(openaire, source_label="openaire")
    openalex_index = build_match_index(openalex, source_label="openalex")

    indexes = {
        "madabi": madabi_index,
        "openaire": openaire_index,
        "openalex": openalex_index,
    }
    write_duplicate_keys_report(indexes)

    madabi_ex = [
        rec
        for rec in madabi
        if not match_details(rec, openaire_index)[0]
        and not match_details(rec, openalex_index)[0]
    ]
    madabi_ex = list({record_identity_key(r): r for r in madabi_ex}.values())

    openaire_ex = exclusive_records(openaire, madabi_index, doi_only=False)
    openalex_ex = exclusive_records(openalex, madabi_index, doi_only=False)
    openaire_strict = strict_exclusive_records(
        openaire, [madabi_index, openalex_index], doi_only=False
    )
    openalex_strict = strict_exclusive_records(
        openalex, [madabi_index, openaire_index], doi_only=False
    )
    open_exclusive = merge_open_exclusive(openaire_ex, openalex_ex)

    summary = build_summary(
        madabi,
        openaire,
        openalex,
        openaire_index,
        openalex_index,
        madabi_ex,
        openaire_ex,
        openalex_ex,
        openaire_strict,
        openalex_strict,
    )

    with open(OUT_SUMMARY_JSON, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    with open(OUT_SUMMARY_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "metric", "value"])
        writer.writeheader()
        writer.writerows(summary_to_csv_rows(summary))

    write_madabi_with_overlap(
        madabi_raw_rows, madabi_fieldnames, madabi, openaire_index, openalex_index
    )
    write_exclusive_csv(OUT_MADABI_EXCLUSIVE, madabi_ex)
    write_exclusive_csv(OUT_OPENAIRE_EXCLUSIVE, openaire_ex)
    write_exclusive_csv(OUT_OPENALEX_EXCLUSIVE, openalex_ex)
    write_exclusive_csv(OUT_OPEN_EXCLUSIVE, open_exclusive)
    write_exclusive_csv(OUT_OPENAIRE_STRICT_EXCLUSIVE, openaire_strict)
    write_exclusive_csv(OUT_OPENALEX_STRICT_EXCLUSIVE, openalex_strict)

    written_oa, written_ox = write_legacy_overlap_exports(
        madabi, openaire_index, openalex_index
    )

    print("Comparison complete.")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote: {OUT_MADABI_UPDATED}")
    print(f"Wrote: {OUT_SUMMARY_JSON}")
    print(f"Wrote: {OUT_SUMMARY_CSV}")
    print(f"Legacy DOI overlaps: OpenAIRE={written_oa}, OpenAlex={written_ox}")


if __name__ == "__main__":
    main()
