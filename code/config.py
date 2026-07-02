"""YAML configuration loading."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from constants import CONFIG_PATH, FIELD_MAPPINGS_PATH


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_field_mappings(path: Optional[Path] = None) -> Dict[str, Any]:
    return load_yaml(path or FIELD_MAPPINGS_PATH)


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    return load_yaml(path or CONFIG_PATH)


def resolve_path(code_dir: Path, rel: str) -> Path:
    return (code_dir / rel).resolve()


def resolve_input_path(source_key: str, code_dir: Path) -> Path:
    cfg = load_field_mappings()["sources"][source_key]
    if "input_candidates" in cfg:
        for rel in cfg["input_candidates"]:
            path = resolve_path(code_dir, rel)
            if path.is_file():
                return path
        tried = "\n".join(f"  - {resolve_path(code_dir, r)}" for r in cfg["input_candidates"])
        raise FileNotFoundError(f"No input for '{source_key}'. Tried:\n{tried}")
    path = resolve_path(code_dir, cfg["input"])
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing input file for source '{source_key}':\n"
            f"  {path}\n"
            f"Place the CSV under data/raw/ or run the corresponding harvest script."
        )
    return path


def resolve_output_path(source_key: str, code_dir: Path) -> Path:
    cfg = load_field_mappings()["sources"][source_key]
    return resolve_path(code_dir, cfg["output"])
