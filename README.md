# madabi\_comparison

This repository compares metadata from the [madabi](https://github.com/UB-Mannheim/madabi/tree/main) harvesting workflow with metadata from **OpenAIRE** and **OpenAlex**. The analysis measures overlap between the three sources and identifies repositories in which datasets with a University of Mannheim affiliation are available in open metadata sources but are not yet covered by the madabi harvest.

## Requirements

* Python 3.11+
* Dependencies: `pip install -r requirements.txt`

## Configuration

* `code/config.yaml` — institution ROR ID and API settings
* `code/field\_mappings.yaml` — per-source column mappings and file paths
* `OPENALEX\_MAILTO` — environment variable with a contact email; recommended when harvesting from OpenAlex

## Included data and reproducibility

The repository includes the input snapshot used for the comparison in `data/raw/`. A new API harvest is therefore **not required** to reproduce the analysis from the committed data.

|File|Role in the workflow|
|-|-|
|`data/raw/unified\_mannheim\_metadata\_cleaned.csv`|MaDaBi input dataset used by the current repository snapshot|
|`data/raw/openaire.csv`|OpenAIRE API-harvest output|
|`data/raw/openalex.csv`|OpenAlex API-harvest output|

An alternative MaDaBi export named `data/raw/unified\_mannheim\_metadata.csv` can optionally be placed in the same directory.

The files in `data/raw/` are working inputs rather than immutable archival copies:

* `dedupe\_sources.py` modifies the OpenAIRE and OpenAlex files in place.
* `run\_pipeline.py --harvest` retrieves fresh records and overwrites `data/raw/openaire.csv` and `data/raw/openalex.csv`.
* To preserve the committed input snapshot, create a copy before running either command or restore the files with Git afterwards.

Generated files are written to `data/processed/`. The repository also contains selected processed outputs as reference material; a complete pipeline run can create additional files or overwrite existing ones.

## Harmonized schema

The three source datasets are harmonized to the following core fields:

`doi`, `title`, `creators`, `repository`, `repository\_method`

|File in `data/processed/`|Description|
|-|-|
|`unified\_mannheim\_metadata\_cleaned.csv`|Harmonized MaDaBi metadata|
|`openaire\_cleaned.csv`|Harmonized OpenAIRE harvest|
|`openalex\_cleaned.csv`|Harmonized OpenAlex harvest|

## Main scripts

|Script|Purpose|
|-|-|
|`code/dedupe\_sources.py`|Deduplicates OpenAIRE and OpenAlex raw CSVs before harmonization|
|`code/clean\_all.py`|Harmonizes all three sources after deduplication|
|`code/clean\_madabi.py`|Harmonizes MaDaBi only|
|`code/clean\_openaire.py`|Harmonizes OpenAIRE only|
|`code/clean\_openalex.py`|Harmonizes OpenAlex only|
|`code/field\_mappings.yaml`|Defines per-source column mappings and file paths|
|`code/openaire.py`|Harvests University of Mannheim datasets from OpenAIRE|
|`code/openalex.py`|Harvests University of Mannheim datasets from OpenAlex|
|`code/compare\_sources.py`|Matches MaDaBi, OpenAIRE and OpenAlex records|
|`code/analyze\_comparison.py`|Creates comparison analyses and the repository-gap report|
|`code/present\_results.py`|Creates German-language outputs for the thesis|
|`code/run\_pipeline.py`|Optional orchestrator; API harvesting is opt-in|

See `code/HARMONIZATION.md` for the normalization rules.

## How to run

Install the dependencies once from the repository root (`madabi\_comparison/`).

### Reproduce the analysis from the included data

This is the recommended command for reproducing the analysis based on the data snapshot committed to the repository. It does not make new API requests.

#### Bash / Git Bash / macOS / Linux

```bash
pip install -r requirements.txt
python code/run\_pipeline.py
```

#### Windows PowerShell

```powershell
pip install -r requirements.txt
python code/run\_pipeline.py
```

The pipeline changes into `code/` for the individual steps automatically. It can therefore be started either from the repository root as shown above or directly from `code/`.

### Run from the `code/` directory

#### Bash / Git Bash / macOS / Linux

```bash
pip install -r requirements.txt
cd code
python run\_pipeline.py
```

#### Windows PowerShell

```powershell
pip install -r requirements.txt
cd code
python run\_pipeline.py
```

### Refresh the external source data via the APIs

Use `--harvest` only when a fresh OpenAIRE and OpenAlex harvest is intended. This overwrites the corresponding files in `data/raw/`.

#### Bash / Git Bash / macOS / Linux

```bash
pip install -r requirements.txt
export OPENALEX\_MAILTO="your.email@example.org"
python code/run\_pipeline.py --harvest
```

#### Windows PowerShell

```powershell
pip install -r requirements.txt
$env:OPENALEX\_MAILTO="your.email@example.org"
python code/run\_pipeline.py --harvest
```

`OPENALEX\_MAILTO` is optional but recommended when harvesting from OpenAlex. It is read from the environment rather than from a configuration file.

## Cleaning and analysis workflow

```text
\[optional: openaire.py + openalex.py harvest]
        ↓
dedupe\_sources.py          # OpenAIRE + OpenAlex raw files only; modifies them in place
        ↓
clean\_all.py               # harmonizes MaDaBi, OpenAIRE and OpenAlex → data/processed/
        ↓
compare\_sources.py         # reads the cleaned source files separately; no merge step
        ↓
analyze\_comparison.py
        ↓
\[optional] present\_results.py
```

|Script|Intended use|
|-|-|
|`dedupe\_sources.py`|Deduplicate OpenAIRE and OpenAlex raw data before harmonization|
|`clean\_all.py`|Harmonize all sources after deduplication|
|`clean\_madabi.py`|Harmonize MaDaBi only (optional)|
|`clean\_openaire.py`|Harmonize OpenAIRE only after deduplication (optional)|
|`clean\_openalex.py`|Harmonize OpenAlex only after deduplication (optional)|

Notes:

* **`clean\_all.py` replaces** the three individual `clean\_\*.py` scripts when all sources should be harmonized.
* Do **not** run `clean\_openaire.py` or `clean\_openalex.py` and then `clean\_all.py` unless overwriting the same processed outputs is intended.
* There is **no** step that combines all cleaned source files into a single file; `compare\_sources.py` reads each harmonized file from `data/processed/` separately.
* **`dedupe\_sources.py` does not modify MaDaBi**; the MaDaBi export is treated as the reference input.

## Recommended manual execution order

From the `code/` directory:

```bash
python dedupe\_sources.py
python clean\_all.py
python compare\_sources.py
python analyze\_comparison.py
```

Equivalent commands from the repository root:

```bash
python code/dedupe\_sources.py
python code/clean\_all.py
python code/compare\_sources.py
python code/analyze\_comparison.py
```

Or use the pipeline runner, which follows the same order and runs deduplication once:

```bash
python code/run\_pipeline.py
```

With `--skip-dedupe`, harmonization still runs through `clean\_all.py`, but raw OpenAIRE and OpenAlex files are not deduplicated. Use this option only when these files are already deduplicated.

Optional thesis outputs in German:

```bash
python code/present\_results.py
```

## Output files (`data/processed/`)

The following files are created by a complete current pipeline run:

|File|Description|
|-|-|
|`dedup\_report.json`|Deduplication statistics|
|`duplicate\_keys\_report.json`|Duplicate DOI/title keys detected during matching|
|`unified\_mannheim\_metadata\_cleaned\_with\_overlap.csv`|MaDaBi records with overlap flags and match metadata|
|`comparison\_summary.json` / `.csv`|Counts plus pairwise and three-way overlaps|
|`madabi\_exclusive.csv`|MaDaBi records not found in OpenAIRE or OpenAlex|
|`openaire\_exclusive.csv`|OpenAIRE records not found in MaDaBi|
|`openalex\_exclusive.csv`|OpenAlex records not found in MaDaBi|
|`openaire\_openalex\_exclusive.csv`|Records from one or both external sources that are not found in MaDaBi|
|`comparison\_report.csv` / `.md`|Analysis summary|
|`repository\_gap\_candidates.csv`|Repositories with datasets not covered by the MaDaBi harvest|

## Matching rules

For each potential record pair, matching follows this priority:

1. Normalized **DOI** (high confidence; used for the core DOI-based overlap metrics)
2. **Exact** title (medium-high confidence)
3. **Normalized** title (medium confidence)

The summary JSON reports DOI-only overlaps separately from overlaps based on all matching methods. The MaDaBi overlap export includes `match\_confidence\_\*` and `overlap\_\*\_doi` columns.

## License

MIT License — see [LICENSE](LICENSE).

