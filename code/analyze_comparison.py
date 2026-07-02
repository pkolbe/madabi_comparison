#!/usr/bin/env python3
"""
Analysis entry point for madabi / OpenAIRE / OpenAlex comparison.

Produces summary reports, repository gap rankings, and markdown output.
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from harmonize_io import load_harmonized_csv
from matching import build_match_index, find_best_match
from repository import normalize_repository

CODE_DIR = Path(__file__).resolve().parent
DATA_PROCESSED = CODE_DIR.parent / "data" / "processed"

FILE_SUMMARY = DATA_PROCESSED / "comparison_summary.json"
FILE_WITH_OVERLAP = DATA_PROCESSED / "unified_mannheim_metadata_cleaned_with_overlap.csv"
FILE_MADABI_CLEANED = DATA_PROCESSED / "unified_mannheim_metadata_cleaned.csv"
FILE_OPENAIRE_CLEANED = DATA_PROCESSED / "openaire_cleaned.csv"
FILE_OPENALEX_CLEANED = DATA_PROCESSED / "openalex_cleaned.csv"
FILE_OPEN_EXCLUSIVE = DATA_PROCESSED / "openaire_openalex_exclusive.csv"
FILE_MADABI_EXCLUSIVE = DATA_PROCESSED / "madabi_exclusive.csv"
FILE_OPENAIRE_EXCLUSIVE = DATA_PROCESSED / "openaire_exclusive.csv"
FILE_OPENALEX_EXCLUSIVE = DATA_PROCESSED / "openalex_exclusive.csv"

OUT_REPORT_CSV = DATA_PROCESSED / "comparison_report.csv"
OUT_REPORT_MD = DATA_PROCESSED / "comparison_report.md"
OUT_GAP_CANDIDATES = DATA_PROCESSED / "repository_gap_candidates.csv"
OUT_GAP_ALL = DATA_PROCESSED / "repository_gap_all.csv"
OUT_MISSING_REPO = DATA_PROCESSED / "missing_repository_report.csv"

MADABI_HARVESTED_SOURCES: Set[str] = {
    "MADATA",
    "GESIS",
    "Harvard Dataverse",
    "Zenodo",
}

CLEANED_SOURCE_FILES = {
    "madabi": FILE_MADABI_CLEANED,
    "openaire": FILE_OPENAIRE_CLEANED,
    "openalex": FILE_OPENALEX_CLEANED,
}


def infer_harvested_sources() -> Set[str]:
    """Add unique repository values from cleaned madabi metadata."""
    sources = set(MADABI_HARVESTED_SOURCES)
    if not FILE_MADABI_CLEANED.is_file():
        return sources
    df = pd.read_csv(FILE_MADABI_CLEANED, dtype=str, keep_default_na=False)
    col = "repository" if "repository" in df.columns else "Source"
    if col in df.columns:
        for value in df[col].unique():
            text = str(value).strip()
            if text:
                sources.add(normalize_repository(text))
    return sources


def load_summary() -> Dict[str, Any]:
    with open(FILE_SUMMARY, encoding="utf-8") as handle:
        return json.load(handle)


def overlap_flag(value: Any) -> bool:
    return str(value).strip() in ("1", "1.0", "True", "true")


def collapse_match_method(method: str) -> str:
    method = str(method).strip()
    if method == "doi":
        return "doi"
    if method in ("title_exact", "title_normalized"):
        return "title_exact"
    return ""


def doi_coverage_report() -> pd.DataFrame:
    rows = []
    for source, path in CLEANED_SOURCE_FILES.items():
        if not path.is_file():
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        total = len(df)
        with_doi = int(df["doi"].astype(str).str.strip().ne("").sum()) if total else 0
        pct = round(100.0 * with_doi / total, 2) if total else 0.0
        rows.append(
            {
                "report_section": "doi_coverage",
                "source": source,
                "total": total,
                "with_doi": with_doi,
                "without_doi": total - with_doi,
                "doi_coverage_pct": pct,
            }
        )
    return pd.DataFrame(rows)


def match_quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target, col in [
        ("openaire", "match_method_openaire"),
        ("openalex", "match_method_openalex"),
    ]:
        if col not in df.columns:
            continue
        matched = df[df["overlap " + target].map(overlap_flag)]
        for bucket in ("doi", "title_exact"):
            count = int(matched[col].map(collapse_match_method).eq(bucket).sum())
            rows.append(
                {
                    "report_section": "match_quality",
                    "target": target,
                    "match_method": bucket,
                    "count": count,
                }
            )
        unmatched = int((~df["overlap " + target].map(overlap_flag)).sum())
        rows.append(
            {
                "report_section": "match_quality",
                "target": target,
                "match_method": "unmatched",
                "count": unmatched,
            }
        )
    return pd.DataFrame(rows)


def madabi_repository_set() -> Set[str]:
    if not FILE_MADABI_CLEANED.is_file():
        return set()
    df = pd.read_csv(FILE_MADABI_CLEANED, dtype=str, keep_default_na=False)
    repos = df["repository"].astype(str).str.strip()
    return {normalize_repository(r) for r in repos.unique() if r}


def missing_repository_report(
    madabi_repos: Set[str],
    madabi_index: Dict[str, Any],
    openaire_index: Dict[str, Any],
    openalex_index: Dict[str, Any],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for source, path in [
        ("openaire", FILE_OPENAIRE_CLEANED),
        ("openalex", FILE_OPENALEX_CLEANED),
    ]:
        if not path.is_file():
            continue
        records = load_harmonized_csv(str(path), source_label=source)
        other_index = openalex_index if source == "openaire" else openaire_index

        repo_counts: Dict[str, int] = defaultdict(int)
        for rec in records:
            repo = normalize_repository(rec.get("repository", ""))
            if repo and repo not in madabi_repos:
                repo_counts[repo] += 1

        for repo, count in sorted(repo_counts.items(), key=lambda x: (-x[1], x[0])):
            rows.append(
                {
                    "report_section": "missing_repository",
                    "metric_type": "repo_absent_from_madabi",
                    "source": source,
                    "repository": repo,
                    "record_count": count,
                }
            )

        empty_repo = [r for r in records if not str(r.get("repository", "")).strip()]
        madabi_hits = sum(1 for r in empty_repo if find_best_match(r, madabi_index)[0])
        cross_hits = sum(1 for r in empty_repo if find_best_match(r, other_index)[0])
        rows.append(
            {
                "report_section": "missing_repository",
                "metric_type": "empty_repository_field",
                "source": source,
                "repository": "",
                "record_count": len(empty_repo),
                "madabi_overlap": madabi_hits,
                "cross_source_overlap": cross_hits,
            }
        )

    return pd.DataFrame(rows)


def open_exclusive_counts_by_repo(path: Path) -> Dict[str, int]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "repository" not in df.columns:
        df["repository"] = df.get("Publisher", "").apply(normalize_repository)
    counts = df.groupby("repository", dropna=False).size()
    return {str(k): int(v) for k, v in counts.items()}


def analyze_madabi_by_source(
    df: pd.DataFrame,
    open_exclusive_by_repo: Optional[Dict[str, int]] = None,
) -> pd.DataFrame:
    source_col = "repository" if "repository" in df.columns else "Source"
    open_exclusive_by_repo = open_exclusive_by_repo or {}
    rows = []
    for source, group in df.groupby(source_col, dropna=False):
        repo_key = str(source).strip()
        madabi_count = len(group)
        open_ex = open_exclusive_by_repo.get(repo_key, 0)
        denom = madabi_count + open_ex
        coverage_ratio = round(madabi_count / denom, 4) if denom else None
        rows.append(
            {
                "report_section": "madabi_by_source",
                "repository": source,
                "total": madabi_count,
                "openaire_overlap": int(group["overlap openaire"].map(overlap_flag).sum()),
                "openaire_no_overlap": int((~group["overlap openaire"].map(overlap_flag)).sum()),
                "openalex_overlap": int(group["overlap openalex"].map(overlap_flag).sum()),
                "openalex_no_overlap": int((~group["overlap openalex"].map(overlap_flag)).sum()),
                "open_exclusive_count": open_ex,
                "coverage_ratio": coverage_ratio,
            }
        )
    return pd.DataFrame(rows)


def madabi_overlap_combos(df: pd.DataFrame) -> pd.DataFrame:
    def category(row) -> str:
        oa = overlap_flag(row.get("overlap openaire"))
        ox = overlap_flag(row.get("overlap openalex"))
        if oa and ox:
            return "Both"
        if oa:
            return "OpenAIRE only"
        if ox:
            return "OpenAlex only"
        return "None"

    counts = df.apply(category, axis=1).value_counts().reset_index()
    counts.columns = ["category", "count"]
    counts.insert(0, "report_section", "madabi_overlap_combos")
    return counts


def exclusive_by_repository(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "repository" not in df.columns:
        pub_col = "Publisher" if "Publisher" in df.columns else "repository_normalized"
        df["repository"] = df.get(pub_col, "").apply(normalize_repository)
    counts = (
        df.groupby("repository", dropna=False)
        .size()
        .reset_index(name="exclusive_count")
        .sort_values("exclusive_count", ascending=False)
    )
    counts.insert(0, "report_section", f"exclusive_by_repository_{label}")
    counts.insert(1, "exclusive_source", label)
    return counts


def _gap_rows_from_exclusive(
    combined: pd.DataFrame,
    harvested: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    if combined.empty:
        return []

    if "repository" not in combined.columns:
        combined = combined.copy()
        combined["repository"] = combined.get("Publisher", "").apply(normalize_repository)
    if "source_system" not in combined.columns:
        combined["source_system"] = combined.get("source", "openaire+openalex")

    mask = combined["repository"].astype(str).str.strip().ne("")
    if harvested is not None:
        mask &= ~combined["repository"].isin(harvested)

    filtered = combined[mask]
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for _, row in filtered.iterrows():
        repo = row.get("repository", "")
        grouped[repo].append(row.to_dict())

    agg_rows = []
    for repo, items in grouped.items():
        seen_keys: Set[str] = set()
        unique_items = []
        for item in items:
            doi = str(item.get("doi", item.get("DOI", ""))).strip().lower()
            title = str(item.get("title", item.get("Title", ""))).strip().lower()
            key = doi if doi else title
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            unique_items.append(item)

        systems = sorted(
            {str(i.get("source_system", i.get("source", ""))) for i in unique_items}
        )
        example = unique_items[0]
        agg_rows.append(
            {
                "repository": example.get("repository", repo),
                "repository_normalized": repo,
                "exclusive_dataset_count": len(unique_items),
                "source_systems": "; ".join(s for s in systems if s),
                "example_doi": example.get("doi", example.get("DOI", "")),
                "example_title": example.get("title", example.get("Title", "")),
            }
        )
    return agg_rows


def build_gap_ranking(harvested: Set[str], scope: str) -> pd.DataFrame:
    if not FILE_OPEN_EXCLUSIVE.is_file():
        return pd.DataFrame()

    combined = pd.read_csv(FILE_OPEN_EXCLUSIVE, dtype=str, keep_default_na=False)
    filter_harvested = harvested if scope == "unharvested" else None
    agg_rows = _gap_rows_from_exclusive(combined, filter_harvested)
    gap_df = pd.DataFrame(agg_rows)
    if gap_df.empty:
        return gap_df
    gap_df.insert(0, "gap_scope", scope)
    return gap_df.sort_values("exclusive_dataset_count", ascending=False).reset_index(drop=True)


def overlap_subset_by_repository(
    records: List[Dict[str, Any]],
    label: str,
) -> pd.DataFrame:
    counts: Dict[str, int] = defaultdict(int)
    for rec in records:
        repo = rec.get("repository") or rec.get("repository_normalized", "")
        repo = normalize_repository(repo) if repo else ""
        counts[repo or "(missing)"] += 1

    rows = [
        {
            "report_section": f"overlap_by_repository_{label}",
            "repository": repo,
            "overlap_count": count,
        }
        for repo, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]
    return pd.DataFrame(rows)


def compute_overlap_subsets() -> Tuple[pd.DataFrame, pd.DataFrame]:
    madabi = load_harmonized_csv(str(FILE_MADABI_CLEANED), source_label="madabi")
    openaire = load_harmonized_csv(str(FILE_OPENAIRE_CLEANED), source_label="openaire")
    openalex = load_harmonized_csv(str(FILE_OPENALEX_CLEANED), source_label="openalex")

    openaire_index = build_match_index(openaire, source_label="openaire")
    openalex_index = build_match_index(openalex, source_label="openalex")

    triple: List[Dict[str, Any]] = []
    for rec in madabi:
        if find_best_match(rec, openaire_index)[0] and find_best_match(
            rec, openalex_index
        )[0]:
            triple.append(rec)

    oa_ox: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for rec in openaire:
        method, matched = find_best_match(rec, openalex_index)
        if not method:
            continue
        doi = rec.get("doi_normalized", "") or (matched or {}).get("doi_normalized", "")
        title = rec.get("title_normalized", "") or (matched or {}).get(
            "title_normalized", ""
        )
        key = f"doi:{doi}" if doi else f"title:{title}"
        if key in seen:
            continue
        seen.add(key)
        oa_ox.append(rec)

    return (
        overlap_subset_by_repository(triple, "triple"),
        overlap_subset_by_repository(oa_ox, "openaire_openalex"),
    )


def summary_report_rows(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    rows = []
    for section, values in summary.items():
        if isinstance(values, dict):
            for metric, value in values.items():
                rows.append(
                    {"report_section": section, "metric": metric, "value": str(value)}
                )
        else:
            rows.append(
                {"report_section": "root", "metric": section, "value": str(values)}
            )
    return rows


def write_markdown(
    summary: Dict[str, Any],
    combos: pd.DataFrame,
    gap_unharvested: pd.DataFrame,
    gap_all: pd.DataFrame,
    harvested: Set[str],
    doi_cov: pd.DataFrame,
    match_quality: pd.DataFrame,
) -> None:
    lines = [
        "# Madabi Comparison Report",
        "",
        "Generated by `code/analyze_comparison.py`.",
        "",
        "## Per-source totals",
        "",
    ]
    totals = summary.get("totals", {})
    for key, value in totals.items():
        lines.append(f"- **{key}**: {value}")

    if not doi_cov.empty:
        lines.extend(["", "## DOI coverage", ""])
        for _, row in doi_cov.iterrows():
            lines.append(
                f"- **{row['source']}**: {row['doi_coverage_pct']}% "
                f"({row['with_doi']}/{row['total']})"
            )

    lines.extend(["", "## Pairwise overlaps — DOI matches (high confidence)", ""])
    for key, value in summary.get("pairwise_overlap_doi", {}).items():
        lines.append(f"- **{key}**: {value}")

    lines.extend(["", "## Pairwise overlaps — any match method", ""])
    for key, value in summary.get("pairwise_overlap_any_method", {}).items():
        lines.append(f"- **{key}**: {value}")

    lines.extend(
        [
            "",
            f"## Three-way overlap (DOI): {summary.get('three_way_overlap_doi', 0)}",
            f"## Three-way overlap (any method): {summary.get('three_way_overlap_any_method', 0)}",
            "",
            "## Exclusive counts (unique)",
            "",
        ]
    )
    for key, value in summary.get("exclusive_unique", {}).items():
        lines.append(f"- **{key}**: {value}")

    strict = summary.get("exclusive_strict_unique", {})
    if strict:
        lines.extend(["", "## Strict exclusive counts (mutually exclusive)", ""])
        for key, value in strict.items():
            lines.append(f"- **{key}**: {value}")

    if not match_quality.empty:
        lines.extend(["", "## Match quality (madabi perspective)", ""])
        for target in match_quality["target"].unique():
            sub = match_quality[match_quality["target"] == target]
            parts = ", ".join(
                f"{r['match_method']}={r['count']}" for _, r in sub.iterrows()
            )
            lines.append(f"- **{target}**: {parts}")

    if not combos.empty:
        lines.extend(["", "## Madabi overlap combinations", ""])
        for _, row in combos.iterrows():
            lines.append(f"- {row['category']}: {row['count']}")

    lines.extend(
        [
            "",
            "## Madabi harvested sources (for unharvested gap analysis)",
            "",
            ", ".join(sorted(harvested)),
            "",
        ]
    )

    if not gap_unharvested.empty:
        lines.extend(["## Top repository gap candidates (unharvested repos)", ""])
        for _, row in gap_unharvested.head(15).iterrows():
            lines.append(
                f"- **{row['repository_normalized']}** "
                f"({row['exclusive_dataset_count']} datasets; "
                f"systems: {row['source_systems']})"
            )

    if not gap_all.empty:
        lines.extend(["", "## Top repository gaps (all repos)", ""])
        for _, row in gap_all.head(10).iterrows():
            lines.append(
                f"- **{row['repository_normalized']}**: "
                f"{row['exclusive_dataset_count']} datasets"
            )

    with open(OUT_REPORT_MD, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    summary = load_summary()
    harvested = infer_harvested_sources()

    report_parts: List[pd.DataFrame] = []
    report_parts.append(pd.DataFrame(summary_report_rows(summary)))

    doi_cov = doi_coverage_report()
    if not doi_cov.empty:
        report_parts.append(doi_cov)
        print("\n=== DOI coverage ===")
        print(doi_cov.to_string(index=False))

    combos = pd.DataFrame()
    match_quality = pd.DataFrame()

    open_exclusive_by_repo = open_exclusive_counts_by_repo(FILE_OPEN_EXCLUSIVE)

    if FILE_WITH_OVERLAP.is_file():
        df = pd.read_csv(FILE_WITH_OVERLAP, dtype=str, keep_default_na=False)
        print("\n=== Overall madabi overlap (from with_overlap file) ===")
        overall = {
            "openaire_overlap": int(df["overlap openaire"].map(overlap_flag).sum()),
            "openaire_no_overlap": int((~df["overlap openaire"].map(overlap_flag)).sum()),
            "openalex_overlap": int(df["overlap openalex"].map(overlap_flag).sum()),
            "openalex_no_overlap": int((~df["overlap openalex"].map(overlap_flag)).sum()),
            "total": len(df),
        }
        print(overall)

        match_quality = match_quality_summary(df)
        report_parts.append(match_quality)
        print("\n=== Match quality ===")
        print(match_quality.to_string(index=False))

        by_source = analyze_madabi_by_source(df, open_exclusive_by_repo)
        print("\n=== By Source ===")
        print(by_source.to_string(index=False))
        report_parts.append(by_source)

        combos = madabi_overlap_combos(df)
        print("\n=== Overlap combinations ===")
        print(combos.to_string(index=False))
        report_parts.append(combos)

        cross = pd.crosstab(
            df["overlap openaire"].map(overlap_flag),
            df["overlap openalex"].map(overlap_flag),
        )
        print("\n=== Cross-tab OpenAIRE x OpenAlex ===")
        print(cross)

    madabi_repos = madabi_repository_set()
    madabi_index = build_match_index(
        load_harmonized_csv(str(FILE_MADABI_CLEANED), source_label="madabi"),
        source_label="madabi",
    )
    openaire_index = build_match_index(
        load_harmonized_csv(str(FILE_OPENAIRE_CLEANED), source_label="openaire"),
        source_label="openaire",
    )
    openalex_index = build_match_index(
        load_harmonized_csv(str(FILE_OPENALEX_CLEANED), source_label="openalex"),
        source_label="openalex",
    )

    missing_repo_df = missing_repository_report(
        madabi_repos, madabi_index, openaire_index, openalex_index
    )
    if not missing_repo_df.empty:
        missing_repo_df.to_csv(OUT_MISSING_REPO, index=False)
        report_parts.append(missing_repo_df)
        print(f"\nWrote missing repository report: {OUT_MISSING_REPO}")

    triple_repo, oa_ox_repo = compute_overlap_subsets()
    for part in (triple_repo, oa_ox_repo):
        if not part.empty:
            report_parts.append(part)

    for label, path in [
        ("madabi", FILE_MADABI_EXCLUSIVE),
        ("openaire", FILE_OPENAIRE_EXCLUSIVE),
        ("openalex", FILE_OPENALEX_EXCLUSIVE),
        ("openaire_openalex", FILE_OPEN_EXCLUSIVE),
    ]:
        part = exclusive_by_repository(path, label)
        if not part.empty:
            report_parts.append(part)

    gap_unharvested = build_gap_ranking(harvested, "unharvested")
    gap_all = build_gap_ranking(harvested, "all")

    gap_unharvested.to_csv(OUT_GAP_CANDIDATES, index=False)
    gap_all.to_csv(OUT_GAP_ALL, index=False)
    print(f"\nWrote gap candidates (unharvested): {OUT_GAP_CANDIDATES}")
    print(f"Wrote gap ranking (all repos): {OUT_GAP_ALL}")

    report = pd.concat(report_parts, ignore_index=True, sort=False)
    report.to_csv(OUT_REPORT_CSV, index=False)
    print(f"\nWrote report: {OUT_REPORT_CSV}")

    if FILE_WITH_OVERLAP.is_file():
        write_markdown(
            summary, combos, gap_unharvested, gap_all, harvested, doi_cov, match_quality
        )
        print(f"Wrote markdown summary: {OUT_REPORT_MD}")


if __name__ == "__main__":
    main()
