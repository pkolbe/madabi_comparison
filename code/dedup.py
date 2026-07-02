"""Within-dataset deduplication for OpenAIRE and OpenAlex raw CSVs."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import resolve_input_path, resolve_output_path
from constants import CODE_DIR, DEDUP_FIELD_KEYS, DEDUP_REPORT_PATH, MISSING_VALUE
from normalize import extract_doi_from_text, is_missing, normalize_doi, normalize_title

DEDUP_SOURCES = ("openaire", "openalex")


def get_first_nonempty(row: Dict[str, Any], candidates: List[str]) -> str:
    for field in candidates:
        value = row.get(field)
        if value is not None and not is_missing(value):
            return str(value).strip()
    return MISSING_VALUE


def _field_candidates(field_map: Dict[str, List[str]], key: str) -> List[str]:
    if key == "repository":
        return field_map.get("repository", field_map.get("publisher", ["Publisher", "Source"]))
    defaults = {
        "doi": ["DOI"],
        "title": ["Title"],
        "creators": ["Creators"],
    }
    return field_map.get(key, defaults.get(key, []))


def doi_key_from_row(row: Dict[str, Any], field_map: Dict[str, List[str]]) -> str:
    raw = get_first_nonempty(row, _field_candidates(field_map, "doi"))
    return normalize_doi(extract_doi_from_text(raw) or raw)


def title_dedup_key_from_row(row: Dict[str, Any], field_map: Dict[str, List[str]]) -> str:
    raw = get_first_nonempty(row, _field_candidates(field_map, "title"))
    return normalize_title(raw)


def metadata_completeness(row: Dict[str, Any], field_map: Dict[str, List[str]]) -> int:
    return sum(
        1
        for key in DEDUP_FIELD_KEYS
        if get_first_nonempty(row, _field_candidates(field_map, key)) != MISSING_VALUE
    )


def dedup_identity_key(row: Dict[str, Any], field_map: Dict[str, List[str]]) -> Tuple[str, str]:
    doi = doi_key_from_row(row, field_map)
    if doi:
        return f"doi:{doi}", "doi"
    title = title_dedup_key_from_row(row, field_map)
    if title:
        return f"title:{title}", "title"
    return "", "none"


def choose_better_row(
    existing: Dict[str, Any],
    candidate: Dict[str, Any],
    existing_idx: int,
    candidate_idx: int,
    field_map: Dict[str, List[str]],
) -> Tuple[int, Dict[str, Any]]:
    e_doi = doi_key_from_row(existing, field_map)
    c_doi = doi_key_from_row(candidate, field_map)
    if bool(e_doi) != bool(c_doi):
        if e_doi:
            return existing_idx, existing
        return candidate_idx, candidate

    e_complete = metadata_completeness(existing, field_map)
    c_complete = metadata_completeness(candidate, field_map)
    if e_complete != c_complete:
        if e_complete > c_complete:
            return existing_idx, existing
        return candidate_idx, candidate

    if existing_idx <= candidate_idx:
        return existing_idx, existing
    return candidate_idx, candidate


def deduplicate_rows(
    rows: List[Dict[str, Any]],
    field_map: Dict[str, List[str]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    kept: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    order: List[str] = []
    stats: Dict[str, Any] = {
        "input_rows": len(rows),
        "removed_total": 0,
        "removed_by_doi": 0,
        "removed_by_title": 0,
        "output_rows": 0,
        "rows_without_doi": 0,
        "rows_without_doi_or_title": 0,
        "unique_keys_doi": 0,
        "unique_keys_title": 0,
        "unique_keys_none": 0,
    }

    for idx, row in enumerate(rows):
        key, key_type = dedup_identity_key(row, field_map)
        if key_type == "none":
            stats["rows_without_doi_or_title"] += 1
            stats["unique_keys_none"] += 1
            slot = f"__none_{idx}"
            kept[slot] = (idx, row)
            order.append(slot)
            continue

        if not doi_key_from_row(row, field_map):
            stats["rows_without_doi"] += 1

        if key not in kept:
            kept[key] = (idx, row)
            order.append(key)
            continue

        prev_idx, prev_row = kept[key]
        winner_idx, winner_row = choose_better_row(
            prev_row, row, prev_idx, idx, field_map
        )
        kept[key] = (winner_idx, winner_row)
        stats["removed_total"] += 1
        if key_type == "doi":
            stats["removed_by_doi"] += 1
        else:
            stats["removed_by_title"] += 1

    result = [kept[k][1] for k in order]
    stats["output_rows"] = len(result)
    stats["unique_keys_doi"] = sum(1 for k in kept if k.startswith("doi:"))
    stats["unique_keys_title"] = sum(1 for k in kept if k.startswith("title:"))
    return result, stats


def validate_deduplicated_rows(
    rows: List[Dict[str, Any]],
    field_map: Dict[str, List[str]],
) -> None:
    seen_doi: set = set()
    seen_title: set = set()
    for row in rows:
        doi = doi_key_from_row(row, field_map)
        if doi:
            if doi in seen_doi:
                raise ValueError(f"Duplicate DOI remains after dedup: {doi}")
            seen_doi.add(doi)
            continue
        title = title_dedup_key_from_row(row, field_map)
        if title:
            if title in seen_title:
                raise ValueError(f"Duplicate title key remains after dedup: {title!r}")
            seen_title.add(title)


def deduplicate_source_file(
    source_key: str,
    code_dir: Optional[Path] = None,
    *,
    in_place: bool = True,
) -> Dict[str, Any]:
    if source_key == "madabi":
        raise ValueError("madabi is already deduplicated; do not run dedup on madabi")

    from config import load_field_mappings

    base = code_dir or CODE_DIR
    cfg = load_field_mappings()["sources"][source_key]
    input_path = resolve_input_path(source_key, base)
    field_map = cfg.get("fields", {})

    with open(input_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        raw_rows = [dict(row) for row in reader]

    deduped, stats = deduplicate_rows(raw_rows, field_map)
    validate_deduplicated_rows(deduped, field_map)

    out_path = input_path if in_place else resolve_output_path(source_key, base)
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deduped)

    return {
        "source": source_key,
        "path": str(out_path),
        **stats,
    }


def run_deduplication(
    code_dir: Optional[Path] = None,
    *,
    sources: Tuple[str, ...] = DEDUP_SOURCES,
    report_path: Path = DEDUP_REPORT_PATH,
) -> Dict[str, Any]:
    """Deduplicate configured sources and write ``dedup_report.json``."""
    base = code_dir or CODE_DIR
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {"sources": {}}

    for source_key in sources:
        summary = deduplicate_source_file(source_key, base, in_place=True)
        report["sources"][source_key] = summary

    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    return report
