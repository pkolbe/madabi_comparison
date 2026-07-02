"""CSV I/O, harmonization, and schema validation.

Named ``harmonize_io`` (not ``io``) to avoid shadowing Python's standard-library
``io`` module when scripts are run from the ``code/`` directory.
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_field_mappings, resolve_input_path, resolve_output_path
from constants import CODE_DIR, MISSING_DOI_TOKENS, MISSING_VALUE, SCHEMA_COLUMNS
from dedup import get_first_nonempty
from normalize import (
    clean_title_display,
    coerce_missing,
    extract_doi_from_text,
    normalize_creators,
    normalize_doi,
    normalize_title,
    title_exact_key,
)
from repository import infer_repository


def _repo_field_candidates(field_map: Dict[str, List[str]]) -> List[str]:
    return field_map.get("repository", field_map.get("publisher", ["Publisher", "Source"]))


def validate_raw_csv_columns(
    source_key: str,
    fieldnames: List[str],
    field_map: Dict[str, List[str]],
    input_path: Path,
) -> None:
    """Ensure a raw source CSV exposes at least one mapped column per required field."""
    if not fieldnames:
        raise ValueError(
            f"Source '{source_key}': input file has no header row: {input_path}"
        )

    missing_groups: List[str] = []
    checks = {
        "doi": field_map.get("doi", ["DOI"]),
        "title": field_map.get("title", ["Title"]),
        "creators": field_map.get("creators", ["Creators"]),
        "repository": _repo_field_candidates(field_map),
    }
    for field, candidates in checks.items():
        if not any(name in fieldnames for name in candidates):
            missing_groups.append(f"{field} (expected one of: {candidates})")

    if missing_groups:
        raise ValueError(
            f"Source '{source_key}': input file is missing required columns.\n"
            f"  File: {input_path}\n"
            f"  Found columns: {fieldnames}\n"
            f"  Missing mappings for: {', '.join(missing_groups)}\n"
            f"  See code/field_mappings.yaml for expected column names."
        )


def harmonize_fields(
    doi_raw: str,
    title_raw: str,
    creators_raw: str,
    repository_raw: str,
) -> Dict[str, str]:
    """Apply unified normalization to produce one harmonized record."""
    doi = normalize_doi(
        extract_doi_from_text(doi_raw)
        or coerce_missing(doi_raw, tokens=MISSING_DOI_TOKENS)
    )
    title = clean_title_display(title_raw)
    creators = normalize_creators(creators_raw)
    repository, repository_method = infer_repository(repository_raw, doi, title)
    return {
        "doi": doi,
        "title": title,
        "creators": creators,
        "repository": repository,
        "repository_method": repository_method,
    }


def validate_schema_columns(columns: List[str]) -> None:
    if list(columns) != SCHEMA_COLUMNS:
        raise ValueError(
            f"Harmonized output schema mismatch.\n"
            f"  Expected columns: {SCHEMA_COLUMNS}\n"
            f"  Got columns: {list(columns)}"
        )


def validate_schema_records(records: List[Dict[str, str]]) -> None:
    """Ensure every harmonized record contains all schema columns."""
    for idx, record in enumerate(records):
        missing = [col for col in SCHEMA_COLUMNS if col not in record]
        if missing:
            raise ValueError(f"Row {idx} missing schema columns: {missing}")
        for col in SCHEMA_COLUMNS:
            if record[col] is None:
                raise ValueError(f"Row {idx} has null value for column '{col}'")


def write_harmonized_csv(path: Path, records: List[Dict[str, str]]) -> None:
    validate_schema_records(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCHEMA_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, MISSING_VALUE) for col in SCHEMA_COLUMNS})


def _is_harmonized_columns(columns: List[str]) -> bool:
    """True when CSV already uses the harmonized schema (with or without legacy 4-col)."""
    if columns == SCHEMA_COLUMNS:
        return True
    legacy = ["doi", "title", "creators", "repository"]
    return columns == legacy


def _comparison_record(
    harmonized: Dict[str, str],
    *,
    source_label: str,
    row_id: int,
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    title = harmonized["title"]
    repository = harmonized["repository"]
    return {
        "source": source_label,
        "row_id": row_id,
        "doi": harmonized["doi"],
        "doi_normalized": harmonized["doi"],
        "title": title,
        "title_normalized": normalize_title(title),
        "title_exact": title_exact_key(title),
        "creators": harmonized["creators"],
        "repository": repository,
        "publisher": repository,
        "repository_normalized": repository,
        "repository_method": harmonized.get("repository_method", ""),
        "raw": raw,
    }


def load_source_csv(
    path: str,
    field_map: Dict[str, List[str]],
    *,
    source_label: str = "",
) -> List[Dict[str, Any]]:
    """Load a CSV, map columns, and apply unified harmonization."""
    input_path = Path(path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Harmonized input file not found: {input_path}")

    records: List[Dict[str, Any]] = []
    with open(input_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        if not _is_harmonized_columns(columns) and field_map:
            validate_raw_csv_columns(source_label or "unknown", columns, field_map, input_path)
        is_harmonized = _is_harmonized_columns(columns)

        for idx, row in enumerate(reader):
            if is_harmonized:
                harmonized = harmonize_fields(
                    row.get("doi", ""),
                    row.get("title", ""),
                    row.get("creators", ""),
                    row.get("repository", ""),
                )
            else:
                harmonized = harmonize_fields(
                    get_first_nonempty(row, field_map.get("doi", ["DOI"])),
                    get_first_nonempty(row, field_map.get("title", ["Title"])),
                    get_first_nonempty(row, field_map.get("creators", ["Creators"])),
                    get_first_nonempty(row, _repo_field_candidates(field_map)),
                )
            records.append(
                _comparison_record(
                    harmonized, source_label=source_label, row_id=idx, raw=dict(row)
                )
            )
    return records


def load_harmonized_csv(path: str, *, source_label: str = "") -> List[Dict[str, Any]]:
    return load_source_csv(path, {}, source_label=source_label)


def harmonize_file(source_key: str, code_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Read a source CSV, harmonize all rows, write harmonized output."""
    base = code_dir or CODE_DIR
    mappings = load_field_mappings()
    if source_key not in mappings.get("sources", {}):
        raise KeyError(
            f"Unknown source '{source_key}'. "
            f"Configured sources: {list(mappings.get('sources', {}).keys())}"
        )

    cfg = mappings["sources"][source_key]
    input_path = resolve_input_path(source_key, base)
    output_path = resolve_output_path(source_key, base)
    field_map = cfg.get("fields", {})

    records: List[Dict[str, str]] = []
    with open(input_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if not _is_harmonized_columns(fieldnames):
            validate_raw_csv_columns(source_key, fieldnames, field_map, input_path)

        for row in reader:
            harmonized = harmonize_fields(
                get_first_nonempty(row, field_map.get("doi", ["DOI"])),
                get_first_nonempty(row, field_map.get("title", ["Title"])),
                get_first_nonempty(row, field_map.get("creators", ["Creators"])),
                get_first_nonempty(row, _repo_field_candidates(field_map)),
            )
            records.append(harmonized)

    if not records:
        print(
            f"Warning: source '{source_key}' produced 0 rows from {input_path}",
            flush=True,
        )

    validate_schema_records(records)
    write_harmonized_csv(output_path, records)

    with open(output_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        validate_schema_columns(list(reader.fieldnames or []))

    return {
        "source": source_key,
        "input": str(input_path),
        "output": str(output_path),
        "rows": len(records),
    }
