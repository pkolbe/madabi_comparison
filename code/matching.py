"""Cross-source record matching and duplicate-key detection."""

from typing import Any, Dict, List, Optional, Tuple

from constants import HIGH_CONFIDENCE_METHODS, MATCH_CONFIDENCE


def is_high_confidence_match(method: Optional[str]) -> bool:
    """Return True when the match method is DOI-based (high confidence)."""
    return method in HIGH_CONFIDENCE_METHODS


def match_confidence_label(method: Optional[str]) -> str:
    if not method:
        return MATCH_CONFIDENCE["none"]
    return MATCH_CONFIDENCE.get(method, "")


def find_best_match(
    record: Dict[str, Any],
    index: Dict[str, Any],
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Find the best match for *record* in a pre-built *index*.

    Priority: DOI > exact title > normalized title.
    Returns ``(match_method, matched_record)`` or ``(None, None)``.
    """
    doi_norm = record.get("doi_normalized", "")
    if doi_norm and doi_norm in index["by_doi"]:
        return "doi", index["by_doi"][doi_norm]

    title_exact = record.get("title_exact", "")
    if title_exact and title_exact in index["by_title_exact"]:
        return "title_exact", index["by_title_exact"][title_exact]

    title_norm = record.get("title_normalized", "")
    if title_norm and title_norm in index["by_title_norm"]:
        return "title_normalized", index["by_title_norm"][title_norm]

    return None, None


def _register_duplicate(
    duplicates: Dict[str, List[Dict[str, Any]]],
    key_type: str,
    key: str,
    rec: Dict[str, Any],
) -> None:
    bucket = f"{key_type}:{key}"
    entry = {
        "source": rec.get("source", ""),
        "row_id": rec.get("row_id"),
        "doi": rec.get("doi_normalized", ""),
        "title": rec.get("title", ""),
    }
    duplicates.setdefault(bucket, []).append(entry)


def build_match_index(
    records: List[Dict[str, Any]],
    *,
    source_label: str = "",
) -> Dict[str, Any]:
    """
    Build lookup indexes from records.

    The first occurrence is used for matching; additional rows sharing the same
    DOI or title key are recorded in ``duplicate_keys`` (not silently dropped).
    """
    by_doi: Dict[str, Dict[str, Any]] = {}
    by_title_exact: Dict[str, Dict[str, Any]] = {}
    by_title_norm: Dict[str, Dict[str, Any]] = {}
    duplicate_keys: Dict[str, List[Dict[str, Any]]] = {}

    for rec in records:
        doi = rec.get("doi_normalized", "")
        if doi:
            if doi in by_doi:
                _register_duplicate(duplicate_keys, "doi", doi, rec)
            else:
                by_doi[doi] = rec

        t_exact = rec.get("title_exact", "")
        if t_exact:
            if t_exact in by_title_exact:
                _register_duplicate(duplicate_keys, "title_exact", t_exact, rec)
            else:
                by_title_exact[t_exact] = rec

        t_norm = rec.get("title_normalized", "")
        if t_norm:
            if t_norm in by_title_norm:
                _register_duplicate(duplicate_keys, "title_normalized", t_norm, rec)
            else:
                by_title_norm[t_norm] = rec

    return {
        "by_doi": by_doi,
        "by_title_exact": by_title_exact,
        "by_title_norm": by_title_norm,
        "records": records,
        "source": source_label,
        "duplicate_keys": duplicate_keys,
    }


def summarize_duplicate_keys(indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate duplicate-key findings from multiple source indexes."""
    by_source: Dict[str, Any] = {}
    total = 0
    for source, index in indexes.items():
        dupes = index.get("duplicate_keys", {})
        count = sum(len(v) for v in dupes.values())
        total += count
        by_source[source] = {
            "duplicate_row_count": count,
            "duplicate_key_count": len(dupes),
            "keys": {
                key: entries for key, entries in sorted(dupes.items())
            },
        }
    return {"total_duplicate_rows": total, "sources": by_source}


def record_identity_key(rec: Dict[str, Any]) -> str:
    """Stable deduplication key: DOI if present, else normalized title."""
    doi = rec.get("doi_normalized", "")
    if doi:
        return f"doi:{doi}"
    title = rec.get("title_normalized", "")
    if title:
        return f"title:{title}"
    return f"row:{rec.get('source', '')}:{rec.get('row_id', '')}"
