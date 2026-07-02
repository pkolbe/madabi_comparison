"""Repository alias mapping and inference."""

from typing import Dict, List, Tuple

from constants import MISSING_VALUE
from normalize import clean_title_display, is_missing, normalize_doi, normalize_title

# Canonical short names -> list of alias substrings (lowercase matching)
REPOSITORY_ALIASES: Dict[str, List[str]] = {
    "MADATA": ["madata", "madat", "Mannheim University Library", "10.7801/"],
    "GESIS": ["gesis", "GESIS Data Archive", "gesis data archive", "10.4232/", "10.7802/"],
    "Harvard Dataverse": ["harvard dataverse", "dataverse harvard", "10.7910/dvn"],
    "Zenodo": ["zenodo", "10.5281/zenodo"],
    "ICPSR": ["icpsr", "10.3886/"],
    "OpenProceedings.org": ["openproceedings", "Open Proceedings", "10.5441/"],
    "Dryad": ["dryad", "10.5061/"],
    "Figshare": ["figshare", "10.6084/"],
    "PsycEXTRA": ["psycextra", "psycextra dataset"],
    "HEPData": ["hepdata", "10.17182/hepdata"],
    "OSF": ["osf.io", "center for open science"],
    "PANGAEA": ["pangaea", "10.1594/"],
    "GBIF": ["gbif", "10.15468/"],
    "OpenAIRE": ["openaire"],
    "OpenAlex": ["openalex"],
    "AUSSDA": ["aussda", "austrian social science data archive"],
    "SAGE Journals": ["sage journals", "sage publications", "10.25384/sage"],
    "Mendeley Data": ["mendeley data", "10.17632/"],
    "IEEE DataPort": ["ieee dataport", "10.21227/"],
    "Borealis": ["borealis", "canadian research data", "10.5683/SP3"],
    "Code Ocean": ["code ocean", "10.24433/co."],
}


def normalize_repository(name: object) -> str:
    """Map repository/publisher/source strings to a canonical short name."""
    if name is None:
        return ""
    s = str(name).strip()
    if not s or s.lower() in ("nan", "none"):
        return ""

    lower = s.lower()
    for canonical, aliases in REPOSITORY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower:
                return canonical

    if "gesis" in lower:
        return "GESIS"
    if "zenodo" in lower:
        return "Zenodo"
    if "dataverse" in lower:
        return "Harvard Dataverse"

    return s


def _match_aliases_in_text(text: str) -> str:
    if not text:
        return MISSING_VALUE
    lower = text.lower()
    for canonical, aliases in REPOSITORY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower:
                return canonical
    return MISSING_VALUE


def infer_repository_from_doi(doi: str) -> str:
    """Infer repository from DOI registrant prefix (longest prefix wins)."""
    doi_norm = normalize_doi(doi)
    if not doi_norm:
        return MISSING_VALUE
    best_canonical = MISSING_VALUE
    best_len = 0
    for canonical, aliases in REPOSITORY_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if not alias_lower.startswith("10."):
                continue
            if doi_norm.startswith(alias_lower) and len(alias_lower) > best_len:
                best_canonical = canonical
                best_len = len(alias_lower)
    return best_canonical


def infer_repository_from_title(title: str) -> str:
    """Weak fallback: match aliases in title text."""
    if is_missing(title):
        return MISSING_VALUE
    for candidate in (clean_title_display(title), normalize_title(title)):
        match = _match_aliases_in_text(candidate)
        if match:
            return match
    return MISSING_VALUE


def infer_repository(
    repository_raw: str,
    doi: str,
    title: str,
) -> Tuple[str, str]:
    """
    Resolve canonical repository.

    Returns ``(repository, method)`` with method in
    ``field``, ``doi_prefix``, ``title``, or ``none``.
    """
    if not is_missing(repository_raw):
        normalized = normalize_repository(repository_raw)
        if normalized:
            return normalized, "field"

    from_doi = infer_repository_from_doi(doi)
    if from_doi:
        return from_doi, "doi_prefix"

    from_title = infer_repository_from_title(title)
    if from_title:
        return from_title, "title"

    return MISSING_VALUE, "none"
