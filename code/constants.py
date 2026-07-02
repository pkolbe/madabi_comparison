"""Shared constants for the madabi comparison pipeline."""

from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

SCHEMA_COLUMNS = ["doi", "title", "creators", "repository", "repository_method"]
MISSING_VALUE = ""
CREATOR_DELIMITER = "; "
MISSING_DOI_TOKENS = frozenset({"", "nan", "none", "na", "n/a", "null", "doi:na"})
MISSING_TEXT_TOKENS = frozenset({"", "nan", "none", "null"})

FIELD_MAPPINGS_PATH = CODE_DIR / "field_mappings.yaml"
CONFIG_PATH = CODE_DIR / "config.yaml"

DEDUP_REPORT_PATH = DATA_PROCESSED / "dedup_report.json"
DUPLICATE_KEYS_REPORT_PATH = DATA_PROCESSED / "duplicate_keys_report.json"

MATCH_CONFIDENCE = {
    "doi": "high",
    "title_exact": "medium-high",
    "title_normalized": "medium",
    "none": "",
}

HIGH_CONFIDENCE_METHODS = frozenset({"doi"})

DEDUP_FIELD_KEYS = ("doi", "title", "creators", "repository")
