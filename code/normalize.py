"""DOI, title, and creator normalization."""

import re
import unicodedata
from typing import Any, List

from constants import CREATOR_DELIMITER, MISSING_DOI_TOKENS, MISSING_TEXT_TOKENS, MISSING_VALUE

DOI_EXTRACT_PATTERN = re.compile(r"(10\.\d{4,9}/\S+)", re.IGNORECASE)


def is_missing(value: Any, *, tokens: frozenset = MISSING_TEXT_TOKENS) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in tokens


def is_missing_doi(value: Any) -> bool:
    return is_missing(value, tokens=MISSING_DOI_TOKENS)


def coerce_missing(value: Any, *, tokens: frozenset = MISSING_TEXT_TOKENS) -> str:
    if is_missing(value, tokens=tokens):
        return MISSING_VALUE
    return str(value).strip()


def normalize_doi(raw: Any) -> str:
    """
    Normalize DOI strings for consistent comparison.

    Handles DOI URLs, ``doi:`` prefixes, whitespace, and case differences.
    Strips simple version suffixes such as ``.v1`` or ``/v1`` at the end.
    """
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    if not s or s in MISSING_DOI_TOKENS:
        return ""
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi[:\s=]+", "", s)
    s = s.strip()
    m = re.match(r"([0-9a-z./\-_]+)", s)
    if m:
        s = m.group(1)
    s = re.sub(r"(\.v|/v)\d+$", "", s)
    if s in MISSING_DOI_TOKENS:
        return ""
    return s


def extract_doi_from_text(value: Any) -> str:
    """
    Extract a DOI token from a messy string (URLs, prose, trailing punctuation).
    Returns an empty string when no DOI-like token is found.
    """
    if is_missing_doi(value):
        return ""
    s = str(value).strip()
    match = DOI_EXTRACT_PATTERN.search(s)
    if not match:
        return ""
    return match.group(1).rstrip("',;:\" ")


def normalize_title(raw: Any, *, strip_parenthetical: bool = True) -> str:
    """
    Normalize titles for fuzzy/exact secondary matching.

    Empty or missing values return an empty string.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none"):
        return ""

    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()

    if strip_parenthetical:
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()

    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def title_exact_key(raw: Any) -> str:
    """Lowercased trimmed title for exact title matching."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    return s.lower()


def clean_title_display(raw: Any) -> str:
    """Display-oriented title for harmonized CSV output."""
    if is_missing(raw):
        return MISSING_VALUE
    s = unicodedata.normalize("NFC", str(raw).strip())
    return re.sub(r"\s+", " ", s)


def _split_creator_tokens(raw: str) -> List[str]:
    """Split on ``;`` or ``|`` only — commas appear inside ``Last, First`` names."""
    return [p.strip() for p in re.split(r"[;|]+", raw) if p.strip()]


def _dedupe_preserve_order(names: List[str]) -> List[str]:
    seen: set = set()
    result: List[str] = []
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def normalize_creators(raw: Any) -> str:
    """Normalize creator lists to ``'; '``-delimited, deduplicated names."""
    if is_missing(raw):
        return MISSING_VALUE
    tokens = _split_creator_tokens(str(raw).strip())
    cleaned = [re.sub(r"\s+", " ", t).strip() for t in tokens]
    cleaned = [t for t in cleaned if t and not is_missing(t)]
    return CREATOR_DELIMITER.join(_dedupe_preserve_order(cleaned))
