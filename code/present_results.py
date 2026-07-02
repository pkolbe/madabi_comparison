#!/usr/bin/env python3
"""
Erzeugt publikationsreife, deutschsprachige Ergebnisdarstellungen für die Thesis.

Liest ausschließlich vorhandene Analyse-Artefakte aus data/processed/ und
schreibt strukturierte Markdown-Texte sowie Word-taugliche Tabellen (CSV).

Voraussetzung: compare_sources.py und analyze_comparison.py wurden ausgeführt.

Verwendung:
    cd code
    python present_results.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_PROCESSED = SCRIPT_DIR.parent / "data" / "processed"
OUT_DIR = DATA_PROCESSED / "thesis_presentation"

# Eingabedateien (von bestehender Pipeline)
INPUT_SUMMARY = DATA_PROCESSED / "comparison_summary.json"
INPUT_REPORT = DATA_PROCESSED / "comparison_report.csv"
INPUT_GAP_ALL = DATA_PROCESSED / "repository_gap_all.csv"
INPUT_GAP_UNHARVESTED = DATA_PROCESSED / "repository_gap_candidates.csv"
INPUT_WITH_OVERLAP = DATA_PROCESSED / "unified_mannheim_metadata_cleaned_with_overlap.csv"

# Bekannte Madabi-Harvest-Quellen (konsistent mit analyze_comparison.py)
HARVESTED_REPOS = frozenset({"MADATA", "GESIS", "Harvard Dataverse", "Zenodo"})


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def pct(part: int, whole: int, digits: int = 1) -> str:
    if whole <= 0:
        return "—"
    return f"{100.0 * part / whole:.{digits}f}"


def pct_float(part: int, whole: int) -> Optional[float]:
    if whole <= 0:
        return None
    return round(100.0 * part / whole, 2)


def load_summary(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_report(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def section_df(report: pd.DataFrame, section: str) -> pd.DataFrame:
    return report[report["report_section"] == section].copy()


def collapse_match_method(method: str) -> str:
    method = str(method).strip()
    if method == "doi":
        return "doi"
    if method in ("title_exact", "title_normalized"):
        return "title_exact"
    return ""


def overlap_flag(value: Any) -> bool:
    return str(value).strip() in ("1", "1.0", "True", "true")


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Einfache Markdown-Tabelle für Word-Import (Pandoc / direktes Einfügen)."""
    lines = [
        "| " + " | ".join(str(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def block_befund(text: str) -> str:
    return f"**Befund.** {text}"


def block_interpretation(text: str) -> str:
    return f"**Interpretation.** {text}"


def block_einschraenkung(text: str) -> str:
    return f"**Einschränkung.** {text}"


def _safe_int(value: Any, default: int = 0) -> int:
    text = str(value).strip()
    if not text:
        return default
    return int(float(text))


def write_csv_table(df: pd.DataFrame, path: Path, caption: str) -> None:
    """CSV mit Metadaten-Zeile für Word-Import dokumentieren."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    meta_path = path.with_suffix(".meta.txt")
    meta_path.write_text(f"Tabellenüberschrift: {caption}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tabellen aus comparison_report.csv
# ---------------------------------------------------------------------------


def table_corpus_overview(summary: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    totals = summary["totals"]
    headers = ["Quelle", "Datensätze (n)", "Eindeutige Schlüssel (n)"]
    rows = [
        ["Madabi", totals["madabi_rows"], totals["madabi_unique"]],
        ["OpenAIRE", totals["openaire_rows"], totals["openaire_unique"]],
        ["OpenAlex", totals["openalex_rows"], totals["openalex_unique"]],
    ]
    return headers, rows


def table_overlap_summary(summary: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    madabi_n = summary["totals"]["madabi_unique"]
    pw = summary["pairwise_overlap_any_method"]
    triple = summary["three_way_overlap_any_method"]
    headers = [
        "Kennzahl",
        "Absolut (n)",
        f"Anteil an Madabi (%) (N={madabi_n})",
    ]
    rows = [
        ["Madabi ∩ OpenAIRE", pw["madabi_openaire"], pct(pw["madabi_openaire"], madabi_n)],
        ["Madabi ∩ OpenAlex", pw["madabi_openalex"], pct(pw["madabi_openalex"], madabi_n)],
        ["Dreifachüberschneidung (Madabi ∩ OpenAIRE ∩ OpenAlex)", triple, pct(triple, madabi_n)],
        ["OpenAIRE ∩ OpenAlex (symmetrisch)", pw["openaire_openalex"], "—"],
    ]
    return headers, rows


COMBO_LABELS_DE = {
    "Both": "Beide Quellen",
    "OpenAIRE only": "Nur OpenAIRE",
    "OpenAlex only": "Nur OpenAlex",
    "None": "Keine externe Überschneidung",
}


def table_overlap_combos(report: pd.DataFrame) -> Tuple[List[str], List[List[Any]]]:
    df = section_df(report, "madabi_overlap_combos")
    headers = ["Kategorie (Madabi-Perspektive)", "Anzahl (n)"]
    rows = [
        [COMBO_LABELS_DE.get(r["category"], r["category"]), int(float(r["count"]))]
        for _, r in df.iterrows()
    ]
    return headers, rows


def table_exclusives(summary: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    loose = summary["exclusive_unique"]
    strict = summary["exclusive_strict_unique"]
    headers = [
        "Quelle",
        "Exklusiv (nicht in Madabi)",
        "Strikt exklusiv (in keiner anderen Quelle)",
    ]
    rows = [
        ["Madabi", strict["madabi"], strict["madabi"]],
        ["OpenAIRE", loose["openaire"], strict["openaire"]],
        ["OpenAlex", loose["openalex"], strict["openalex"]],
    ]
    return headers, rows


def table_doi_coverage(report: pd.DataFrame) -> Tuple[List[str], List[List[Any]]]:
    df = section_df(report, "doi_coverage")
    headers = ["Quelle", "Gesamt (n)", "Mit DOI (n)", "Ohne DOI (n)", "DOI-Abdeckung (%)"]
    rows = []
    for _, r in df.iterrows():
        rows.append(
            [
                r["source"],
                r["total"],
                r["with_doi"],
                r["without_doi"],
                r["doi_coverage_pct"],
            ]
        )
    return headers, rows


def table_match_quality(report: pd.DataFrame, madabi_n: int) -> Tuple[List[str], List[List[Any]]]:
    df = section_df(report, "match_quality")
    headers = [
        "Zielquelle",
        "Match-Typ",
        "Anzahl (n)",
        "Anteil an Madabi (%)",
        "Anteil an Treffern (%)",
    ]
    rows: List[List[Any]] = []
    for target in ("openaire", "openalex"):
        sub = df[df["target"] == target]
        matched_n = int(
            sub[sub["match_method"].isin(["doi", "title_exact"])]["count"].astype(float).sum()
        )
        for _, r in sub.iterrows():
            method = r["match_method"]
            count = int(float(r["count"]))
            share_madabi = pct(count, madabi_n) if method != "unmatched" else pct(count, madabi_n)
            share_matched = (
                pct(count, matched_n) if method in ("doi", "title_exact") and matched_n else "—"
            )
            label = {
                "doi": "DOI",
                "title_exact": "Titel (normalisiert, exakt)",
                "unmatched": "Kein Treffer",
            }.get(method, method)
            rows.append([target.capitalize(), label, count, share_madabi, share_matched])
    return headers, rows


def table_madabi_by_source(report: pd.DataFrame) -> Tuple[List[str], List[List[Any]]]:
    df = section_df(report, "madabi_by_source")
    headers = [
        "Repository",
        "Madabi (n)",
        "Überschneidung OpenAIRE (n)",
        "Überschneidung OpenAlex (n)",
        "Open-Exklusiv (n)",
        "Abdeckungsgrad",
    ]
    rows = []
    for _, r in df.iterrows():
        ratio = float(r["coverage_ratio"]) if r["coverage_ratio"] else None
        ratio_fmt = f"{ratio:.4f}" if ratio is not None else "—"
        rows.append(
            [
                r["repository"],
                int(float(r["total"])),
                int(float(r["openaire_overlap"])),
                int(float(r["openalex_overlap"])),
                int(float(r["open_exclusive_count"])),
                ratio_fmt,
            ]
        )
    return headers, rows


def table_gap_ranking(path: Path, top_n: Optional[int] = None) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.empty:
        return df
    df["exclusive_dataset_count"] = df["exclusive_dataset_count"].astype(int)
    df = df.sort_values("exclusive_dataset_count", ascending=False)
    if top_n is not None:
        df = df.head(top_n)
    return df


def gap_table_rows(df: pd.DataFrame) -> Tuple[List[str], List[List[Any]]]:
    headers = ["Rang", "Repository", "Anzahl exklusiver Datensätze (n)", "Quellsysteme"]
    rows = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        rows.append([i, r["repository_normalized"], r["exclusive_dataset_count"], r["source_systems"]])
    return headers, rows


def overlap_crosstab(with_overlap_path: Path) -> Tuple[List[str], List[List[Any]]]:
    df = pd.read_csv(with_overlap_path, dtype=str, keep_default_na=False)
    headers = ["", "Kein OpenAlex-Treffer", "OpenAlex-Treffer"]
    rows: List[List[Any]] = []
    for oa_label, oa_val in [("Kein OpenAIRE-Treffer", False), ("OpenAIRE-Treffer", True)]:
        row = [oa_label]
        for ox_val in (False, True):
            n = int(
                (
                    (df["overlap openaire"].map(overlap_flag) == oa_val)
                    & (df["overlap openalex"].map(overlap_flag) == ox_val)
                ).sum()
            )
            row.append(n)
        rows.append(row)
    return headers, rows


# ---------------------------------------------------------------------------
# Dokumentgenerierung
# ---------------------------------------------------------------------------


def build_definitions_section() -> str:
    return "\n".join(
        [
            "## Operative Definitionen",
            "",
            block_befund(
                "Die folgenden Begriffe beziehen sich auf die harmonisierten "
                "Vier-Spalten-Metadaten (`doi`, `title`, `creators`, `repository`) "
                "und die in `compare_sources.py` implementierte Abgleichlogik."
            ),
            "",
            md_table(
                ["Begriff", "Definition"],
                [
                    [
                        "Überschneidung (Overlap)",
                        "Zwei Datensätze gelten als übereinstimmend, wenn der normalisierte "
                        "DOI übereinstimmt oder der normalisierte Titel exakt übereinstimmt "
                        "(Priorität: DOI vor Titel).",
                    ],
                    [
                        "Eindeutiger Schlüssel",
                        "DOI, sofern vorhanden; andernfalls normalisierter Titel.",
                    ],
                    [
                        "Exklusiv (nicht-strikt, OpenAIRE/OpenAlex)",
                        "Datensatz der externen Quelle ohne Treffer in Madabi "
                        "(kann in der jeweils anderen externen Quelle vorkommen).",
                    ],
                    [
                        "Strikt exklusiv",
                        "Datensatz kommt in keiner der beiden anderen Quellen vor.",
                    ],
                    [
                        "Dreifachüberschneidung",
                        "Madabi-Datensätze mit gleichzeitigem Treffer in OpenAIRE und OpenAlex.",
                    ],
                    [
                        "Abdeckungsgrad (Repository)",
                        "Madabi-Anzahl / (Madabi-Anzahl + Open-Exklusiv-Anzahl) je Repository.",
                    ],
                    [
                        "Gap (Lücke)",
                        "In OpenAIRE und/oder OpenAlex verzeichnete Datensätze, die nicht in "
                        "Madabi enthalten sind, gruppiert nach Repository.",
                    ],
                    [
                        "Titel-Match (Berichtskategorie title_exact)",
                        "Übereinstimmung über normalisierten Titel (einschließlich der "
                        "technischen Kategorie `title_normalized` in den Rohdaten).",
                    ],
                ],
            ),
            "",
        ]
    )


def build_main_document(
    summary: Dict[str, Any],
    report: pd.DataFrame,
    generated_at: str,
) -> str:
    madabi_n = summary["totals"]["madabi_unique"]
    parts: List[str] = [
        "# Ergebnisdarstellung: Vergleich Madabi, OpenAIRE und OpenAlex",
        "",
        f"*Erstellt am {generated_at} durch `code/present_results.py` "
        f"auf Basis der Pipeline-Artefakte in `data/processed/`.*",
        "",
        "---",
        "",
        "## Einleitung",
        "",
        block_befund(
            "Dieses Dokument fasst die Ergebnisse des systematischen Metadatenvergleichs "
            "zwischen dem lokalen Madabi-Bestand (Referenzkorpus) und den externen "
            "Quellen OpenAIRE sowie OpenAlex zusammen. Madabi dient als Referenzsystem; "
            "die externen Quellen ermöglichen eine unabhängige Überprüfung der "
            "Auffindbarkeit und Abdeckung."
        ),
        "",
        block_interpretation(
            "Die Darstellung unterscheidet ausdrücklich zwischen deskriptiven Befunden "
            "(absoluten und relativen Häufigkeiten) und vorsichtigen Interpretationen, "
            "die erst im Diskussionsteil der Arbeit vertieft werden sollten."
        ),
        "",
        build_definitions_section(),
        "",
        "## 1. Überblick über die Datensätze und Vergleichslogik",
        "",
        block_befund(
            "Tabelle 1 zeigt die Umfänge der harmonisierten Bestände nach Quelle."
        ),
        "",
        "*Tabelle 1. Umfang der harmonisierten Metadatenbestände.*",
        "",
        md_table(*table_corpus_overview(summary)),
        "",
        block_einschraenkung(
            "Die Bestände sind nicht als gleich große Populationen zu interpretieren. "
            "OpenAIRE und OpenAlex wurden über organisationsbezogene API-Abfragen "
            "gewonnen und unterliegen unterschiedlichen Erfassungslogiken."
        ),
        "",
        "## 2. Überschneidungen zwischen Quellen",
        "",
        block_befund(
            "Tabelle 2 berichtet paarweise und dreifache Überschneidungen auf Basis "
            "eindeutiger Schlüssel. Tabelle 3 zeigt die Kombinationen aus Madabi-Perspektive."
        ),
        "",
        "*Tabelle 2. Überschneidungen (eindeutige Datensätze).*",
        "",
        md_table(*table_overlap_summary(summary)),
        "",
        "*Tabelle 3. Überschneidungskombinationen aus Madabi-Perspektive.*",
        "",
        md_table(*table_overlap_combos(report)),
        "",
    ]

    if INPUT_WITH_OVERLAP.is_file():
        parts.extend(
            [
                "*Tabelle 4. Kontingenztabelle: Madabi-Datensätze nach OpenAIRE- und "
                "OpenAlex-Treffer (n).*",
                "",
                md_table(*overlap_crosstab(INPUT_WITH_OVERLAP)),
                "",
            ]
        )

    parts.extend(
        [
            block_interpretation(
                f"Von {madabi_n} Madabi-Datensätzen weisen {summary['pairwise_overlap_any_method']['madabi_openaire']} "
                f"({pct(summary['pairwise_overlap_any_method']['madabi_openaire'], madabi_n)} %) einen Treffer "
                f"in OpenAIRE auf, {summary['pairwise_overlap_any_method']['madabi_openalex']} "
                f"({pct(summary['pairwise_overlap_any_method']['madabi_openalex'], madabi_n)} %) in OpenAlex. "
                f"Die dreifache Überschneidung umfasst {summary['three_way_overlap_any_method']} Datensätze "
                f"({pct(summary['three_way_overlap_any_method'], madabi_n)} %)."
            ),
            "",
            block_einschraenkung(
                "Paarweise Überschneidungen zwischen OpenAIRE und OpenAlex (symmetrisch) "
                "sind nicht mit der dreifachen Überschneidung auf Madabi-Basis identisch."
            ),
            "",
            "## 3. Exklusive Datensätze",
            "",
            block_befund(
                "Tabelle 5 unterscheidet nicht-strikte Exklusivität (bezogen auf Madabi) "
                "von strikt exklusiven Mengen, die sich gegenseitig ausschließen."
            ),
            "",
            "*Tabelle 5. Exklusive Datensätze.*",
            "",
            md_table(*table_exclusives(summary)),
            "",
            block_interpretation(
                "Für Aussagen über eine vollständige dreiteilige Partition der "
                "Gesamtheit aller Datensätze sind die strikt exklusiven Mengen maßgeblich. "
                "Die nicht-strikten OpenAIRE-Exklusivzahlen können Datensätze enthalten, "
                "die in OpenAlex vorhanden sind."
            ),
            "",
            "## 4. DOI-Abdeckung und Metadatenqualität",
            "",
            block_befund("Tabelle 6 berichtet die DOI-Verfügbarkeit je Quelle."),
            "",
            "*Tabelle 6. DOI-Abdeckung in den harmonisierten Beständen.*",
            "",
            md_table(*table_doi_coverage(report)),
            "",
            block_einschraenkung(
                "Eine hohe DOI-Abdeckung ist Voraussetzung für zuverlässige DOI-basierte "
                "Verknüpfung, ersetzt jedoch keine inhaltliche Validierung der Metadaten."
            ),
            "",
            "## 5. Repository-spezifische Analysen",
            "",
            block_befund(
                "Tabelle 7 fasst Madabi-Bestände nach Repository zusammen und gibt "
                "Überschneidungszahlen, Open-Exklusivzahlen sowie den Abdeckungsgrad an."
            ),
            "",
            "*Tabelle 7. Repository-spezifische Kennzahlen (Madabi-Harvest-Quellen).*",
            "",
            md_table(*table_madabi_by_source(report)),
            "",
            block_interpretation(
                "Ein niedriger Abdeckungsgrad bei gleichzeitig hoher Open-Exklusivzahl "
                "weist auf eine Konzentration extern auffindbarer, aber in Madabi nicht "
                "enthaltener Datensätze in diesem Repository hin. Dies ist deskriptiv "
                "und nicht automatisch als Harvest-Ausfall zu werten."
            ),
            "",
            block_einschraenkung(
                "Repository-Zuordnungen basieren auf harmonisierten Publisher-/Source-Feldern "
                "und ggf. DOI-Präfix-Inferenz; Fehlklassifikationen sind möglich."
            ),
            "",
            "## 6. Matching-Qualität (DOI vs. Titel-Match)",
            "",
            block_befund(
                "Tabelle 8 zeigt, über welche Match-Typen Madabi-Datensätze mit den "
                "externen Quellen verknüpft wurden. Für die Berichterstattung werden "
                "ausschließlich die Kategorien DOI und Titel (normalisiert, exakt) verwendet."
            ),
            "",
            "*Tabelle 8. Verteilung der Match-Typen (Madabi-Perspektive).*",
            "",
            md_table(*table_match_quality(report, madabi_n)),
            "",
            block_interpretation(
                "DOI-Matches sind methodisch robuster als Titel-Matches. Titel-basierte "
                "Treffer sollten in einer vertiefenden Qualitätsprüfung stichprobenartig "
                "validiert werden."
            ),
            "",
            block_einschraenkung(
                "OpenAlex weist im Vergleich zu OpenAIRE eine geringere Trefferquote "
                "auf Madabi auf; dies spiegelt primär geringere Überschneidung wider, "
                "nicht notwendigerweise eine schlechtere Matcher-Implementierung."
            ),
            "",
            "## 7. Gap-Analyse (Madabi vs. externe Quellen)",
            "",
            block_befund(
                "Die Gap-Analyse identifiziert Datensätze, die in OpenAIRE und/oder "
                "OpenAlex, nicht jedoch in Madabi enthalten sind. Tabelle 9 fokussiert "
                "Repositories außerhalb des bekannten Madabi-Harvest-Sets; "
                "vollständige Ranglisten siehe Anhang."
            ),
            "",
        ]
    )

    gap_unharvested = table_gap_ranking(INPUT_GAP_UNHARVESTED, top_n=15)
    if not gap_unharvested.empty:
        parts.extend(
            [
                "*Tabelle 9. Priorisierte Repository-Lücken (nicht geharvestete Repositories, Top 15).*",
                "",
                md_table(*gap_table_rows(gap_unharvested)),
                "",
            ]
        )

    gap_harvested = table_gap_ranking(INPUT_GAP_ALL)
    if not gap_harvested.empty:
        harvested_only = gap_harvested[
            gap_harvested["repository_normalized"].isin(HARVESTED_REPOS)
        ].head(5)
        if not harvested_only.empty:
            parts.extend(
                [
                    "*Tabelle 10. Größte Lücken in bereits geharvesteten Repositories (Auszug).*",
                    "",
                    md_table(*gap_table_rows(harvested_only)),
                    "",
                ]
            )

    parts.extend(
        [
            block_interpretation(
                "Repositories mit hohen Exklusivzahlen außerhalb des Harvest-Sets "
                "(z. B. Figshare, ICPSR) sind Kandidaten für eine Erweiterung des "
                "Harvest-Portfolios. Hohe Lücken in geharvesteten Repositories "
                "(z. B. Harvard Dataverse, GESIS) legen eher eine Prüfung der "
                "Harvest-Regeln und Filter nahe."
            ),
            "",
            block_einschraenkung(
                "Exklusivzahlen sind keine Normativität: Nicht jeder extern "
                "auffindbare Datensatz muss zwingend in Madabi enthalten sein "
                "(z. B. aufgrund von Erfassungsgrenzen, Dubletten oder "
                "Affiliations-Rauschen in den APIs)."
            ),
            "",
            "## 8. Zusammenfassung der Hauptergebnisse",
            "",
            block_befund(
                f"Der Madabi-Referenzbestand umfasst {madabi_n} eindeutige Datensätze. "
                f"Die Überschneidung mit OpenAIRE beträgt {pct(summary['pairwise_overlap_any_method']['madabi_openaire'], madabi_n)} %, "
                f"mit OpenAlex {pct(summary['pairwise_overlap_any_method']['madabi_openalex'], madabi_n)} %. "
                f"{summary['exclusive_strict_unique']['madabi']} Datensätze sind strikt exklusiv in Madabi. "
                f"In externen Quellen ohne Madabi-Entsprechung wurden {summary['exclusive_unique']['openaire_or_openalex_not_madabi']} "
                f"deduplizierte Datensätze identifiziert."
            ),
            "",
            "---",
            "",
            "*Hinweis zur Übernahme in Word:* Markdown-Datei öffnen oder per Pandoc "
            "konvertieren (`pandoc thesis_ergebnisse.md -o thesis_ergebnisse.docx`). "
            "Tabellen liegen zusätzlich als CSV (UTF-8 mit BOM) in `thesis_presentation/tabellen/` vor.",
            "",
        ]
    )

    return "\n".join(parts)


def build_appendix_document(summary: Dict[str, Any], report: pd.DataFrame) -> str:
    parts: List[str] = [
        "# Anhang: Vollständige Tabellen",
        "",
        "Ergänzende deskriptive Tabellen zur Übernahme in den Anhang der Arbeit.",
        "",
    ]

    # Exklusiv nach Repository
    for section, title in [
        ("exclusive_by_repository_madabi", "A.1 Madabi-exklusive Datensätze nach Repository"),
        (
            "exclusive_by_repository_openaire_openalex",
            "A.2 Open-Source-exklusive Datensätze nach Repository (dedupliziert)",
        ),
        ("overlap_by_repository_triple", "A.3 Dreifachüberschneidung nach Repository"),
        (
            "overlap_by_repository_openaire_openalex",
            "A.4 Überschneidung OpenAIRE ∩ OpenAlex nach Repository",
        ),
    ]:
        df = section_df(report, section)
        if df.empty:
            continue
        parts.append(f"## {title}")
        parts.append("")
        if "exclusive_count" in df.columns:
            headers = ["Repository", "Anzahl (n)"]
            rows = [
                [r["repository"] or "(fehlend)", _safe_int(r["exclusive_count"])]
                for _, r in df.iterrows()
            ]
        elif "overlap_count" in df.columns:
            headers = ["Repository", "Anzahl (n)"]
            rows = [
                [r["repository"] or "(fehlend)", _safe_int(r["overlap_count"])]
                for _, r in df.iterrows()
            ]
        else:
            continue
        parts.append(md_table(headers, rows))
        parts.append("")

    # Vollständige Gap-Rankings
    for path, heading in [
        (INPUT_GAP_UNHARVESTED, "A.5 Gap-Ranking: nicht geharvestete Repositories"),
        (INPUT_GAP_ALL, "A.6 Gap-Ranking: alle Repositories"),
    ]:
        df = table_gap_ranking(path)
        if df.empty:
            continue
        parts.extend(
            [
                f"## {heading}",
                "",
                md_table(
                    ["Rang", "Repository", "n", "Beispiel-DOI", "Quellsysteme"],
                    [
                        [
                            i,
                            r["repository_normalized"],
                            r["exclusive_dataset_count"],
                            r.get("example_doi", ""),
                            r.get("source_systems", ""),
                        ]
                        for i, (_, r) in enumerate(df.iterrows(), start=1)
                    ],
                ),
                "",
            ]
        )

    # Missing repository
    miss = section_df(report, "missing_repository")
    if not miss.empty:
        parts.extend(["## A.7 Fehlende Repository-Zuordnungen und externe Repositories", ""])
        absent = miss[miss["metric_type"] == "repo_absent_from_madabi"]
        if not absent.empty:
            parts.append("### Repositories in externen Quellen ohne Vorkommen in Madabi")
            parts.append("")
            parts.append(
                md_table(
                    ["Quelle", "Repository", "Anzahl (n)"],
                    [
                        [r["source"], r["repository"], _safe_int(r["record_count"])]
                        for _, r in absent.iterrows()
                    ],
                )
            )
            parts.append("")
        empty = miss[miss["metric_type"] == "empty_repository_field"]
        if not empty.empty:
            parts.append("### Datensätze mit leerem Repository-Feld")
            parts.append("")
            parts.append(
                md_table(
                    ["Quelle", "Anzahl (n)", "Madabi-Überschneidung", "Überschneidung andere Ext.-Quelle"],
                    [
                        [
                            r["source"],
                            _safe_int(r["record_count"]),
                            _safe_int(r["madabi_overlap"]),
                            _safe_int(r["cross_source_overlap"]),
                        ]
                        for _, r in empty.iterrows()
                    ],
                )
            )
            parts.append("")

    parts.append(
        "## A.8 Reproduzierbarkeit\n\n"
        "Quelldateien: `comparison_summary.json`, `comparison_report.csv`, "
        "`repository_gap_all.csv`, `repository_gap_candidates.csv`, "
        "`unified_mannheim_metadata_cleaned_with_overlap.csv`.\n\n"
        "Erzeugungsskripte: `compare_sources.py`, `analyze_comparison.py`, `present_results.py`."
    )

    return "\n".join(parts)


def export_word_tables(
    summary: Dict[str, Any],
    report: pd.DataFrame,
) -> List[Path]:
    """Schreibt nummerierte CSV-Tabellen für direkten Word-Import."""
    tables_dir = OUT_DIR / "tabellen"
    tables_dir.mkdir(parents=True, exist_ok=True)
    madabi_n = summary["totals"]["madabi_unique"]
    written: List[Path] = []

    specs: List[Tuple[str, str, List[str], List[List[Any]]]] = [
        ("tabelle_01_korpus.csv", "Tabelle 1: Umfang der Metadatenbestände", *table_corpus_overview(summary)),
        ("tabelle_02_ueberschneidungen.csv", "Tabelle 2: Überschneidungen", *table_overlap_summary(summary)),
        ("tabelle_03_kombinationen.csv", "Tabelle 3: Überschneidungskombinationen (Madabi)", *table_overlap_combos(report)),
        ("tabelle_05_exklusiv.csv", "Tabelle 5: Exklusive Datensätze", *table_exclusives(summary)),
        ("tabelle_06_doi_abdeckung.csv", "Tabelle 6: DOI-Abdeckung", *table_doi_coverage(report)),
        ("tabelle_07_repository.csv", "Tabelle 7: Repository-Kennzahlen", *table_madabi_by_source(report)),
        ("tabelle_08_matching.csv", "Tabelle 8: Match-Typen", *table_match_quality(report, madabi_n)),
    ]

    if INPUT_WITH_OVERLAP.is_file():
        h, r = overlap_crosstab(INPUT_WITH_OVERLAP)
        specs.insert(
            3,
            ("tabelle_04_kontingenz.csv", "Tabelle 4: Kontingenztabelle Madabi", h, r),
        )

    gap_u = table_gap_ranking(INPUT_GAP_UNHARVESTED, top_n=15)
    if not gap_u.empty:
        specs.append(
            ("tabelle_09_gap_unharvested.csv", "Tabelle 9: Gap-Ranking (nicht geharvestet)", *gap_table_rows(gap_u))
        )

    for filename, caption, headers, rows in specs:
        path = tables_dir / filename
        df = pd.DataFrame(rows, columns=headers)
        write_csv_table(df, path, caption)
        written.append(path)

    return written


def write_index(summary: Dict[str, Any], outputs: List[Path], generated_at: str) -> None:
    index = {
        "generated_at": generated_at,
        "script": "code/present_results.py",
        "inputs": {
            "comparison_summary": str(INPUT_SUMMARY),
            "comparison_report": str(INPUT_REPORT),
            "repository_gap_all": str(INPUT_GAP_ALL),
            "repository_gap_unharvested": str(INPUT_GAP_UNHARVESTED),
            "with_overlap": str(INPUT_WITH_OVERLAP),
        },
        "outputs": [str(p) for p in outputs],
        "summary_snapshot": summary,
    }
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def validate_inputs() -> None:
    required = [INPUT_SUMMARY, INPUT_REPORT]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            "Erforderliche Eingabedateien fehlen. Bitte zuerst die Pipeline ausführen:\n"
            "  python compare_sources.py\n"
            "  python analyze_comparison.py\n"
            f"Fehlend: {', '.join(missing)}"
        )


def main() -> None:
    validate_inputs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = load_summary(INPUT_SUMMARY)
    report = load_report(INPUT_REPORT)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    main_path = OUT_DIR / "thesis_ergebnisse.md"
    appendix_path = OUT_DIR / "thesis_anhang.md"

    main_path.write_text(build_main_document(summary, report, generated_at), encoding="utf-8")
    appendix_path.write_text(build_appendix_document(summary, report), encoding="utf-8")

    table_paths = export_word_tables(summary, report)
    all_outputs = [main_path, appendix_path, *table_paths]
    write_index(summary, all_outputs, generated_at)

    print(f"Ergebnisdarstellung erstellt: {OUT_DIR}")
    print(f"  Haupttext:    {main_path}")
    print(f"  Anhang:       {appendix_path}")
    print(f"  Tabellen:     {len(table_paths)} CSV-Dateien in {OUT_DIR / 'tabellen'}")
    print(f"  Index:        {OUT_DIR / 'index.json'}")


if __name__ == "__main__":
    main()
