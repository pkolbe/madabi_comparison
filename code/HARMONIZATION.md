# Metadata Harmonization

All cleaned outputs share this schema (and **only** these columns):

`doi`, `title`, `creators`, `repository`, `repository_method`

| Column | Description |
|--------|-------------|
| `doi` | Normalized DOI |
| `title` | Display title (case preserved) |
| `creators` | Semicolon-delimited creator list |
| `repository` | Canonical repository name |
| `repository_method` | How repository was resolved: `field`, `doi_prefix`, `title`, or `none` |

## Pipeline order

```text
dedupe_sources.py  →  clean_all.py  →  compare_sources.py
```

Deduplication and harmonization are separate steps:

| Script | Intended use | Deduplicates? | Writes |
|--------|--------------|---------------|--------|
| `dedupe_sources.py` | Deduplicate OpenAIRE and OpenAlex raw CSVs | Yes (raw, in-place) | `data/processed/dedup_report.json` |
| `clean_all.py` | Harmonize all sources | No | All `data/processed/*_cleaned.csv` |
| `clean_madabi.py` | Harmonize MADABI only | No | `unified_mannheim_metadata_cleaned.csv` |
| `clean_openaire.py` | Harmonize OpenAIRE only | No | `openaire_cleaned.csv` |
| `clean_openalex.py` | Harmonize OpenAlex only | No | `openalex_cleaned.csv` |

- Run `dedupe_sources.py` before `clean_all.py` (or before `clean_openaire.py` / `clean_openalex.py`).
- `clean_all.py` does not combine sources; `compare_sources.py` loads each harmonized file separately.
- Do not run per-source clean scripts and then `clean_all.py` unless you intend to overwrite processed outputs.

Field mappings: `code/field_mappings.yaml`  
Shared logic: `code/normalize.py`, `code/repository.py`, `code/harmonize_io.py`

## Normalization (same rules for all sources)

| Field | Rule |
|-------|------|
| **Missing** | Empty string `""` |
| **doi** | Extract token, lowercase, strip `https://doi.org/`, remove `.v1`/`/v1`; `na` → missing |
| **title** | Trim, NFC unicode, collapse whitespace (case preserved in output) |
| **creators** | Split on `;` or `|`; dedupe; join with `"; "` |
| **repository** | See inference chain below |
| **repository_method** | Provenance of repository resolution |

Title **matching** (in `compare_sources.py`) uses `normalize_title()` separately (lowercase, punctuation stripped).

## Repository inference

Priority:

1. **Field** — `Source` (MADABI) or `Publisher` (OpenAIRE/OpenAlex), via `normalize_repository()`
2. **DOI prefix** — longest match against `REPOSITORY_ALIASES` (e.g. `10.7801` → MADATA)
3. **Title** — weak fallback: alias substring in title (low confidence)

## Matching confidence

Core summary metrics distinguish:

- **DOI matches** (`pairwise_overlap_doi`) — high confidence
- **Any method** (`pairwise_overlap_any_method`) — includes title-based matches

The madabi overlap export includes `overlap_openaire_doi` / `overlap_openalex_doi` flags for DOI-only overlaps.

## Deduplication (openaire / openalex only)

`dedupe_sources.py` deduplicates within each raw CSV (only entry point that modifies raw files):

1. **DOI** — normalized DOI as primary key
2. **Title** — normalized title when DOI is missing

Report: `data/processed/dedup_report.json`. **MADABI is not deduplicated** by this step.

## Run

```bash
cd code
python dedupe_sources.py
python clean_all.py
python compare_sources.py
```

Or: `python run_pipeline.py` (runs the same steps in order).
