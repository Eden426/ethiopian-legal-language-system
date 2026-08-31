"""Loading and validation for experiment configuration."""

from pathlib import Path
from typing import Any

import yaml


REQUIRED_SECTIONS = {"model", "data", "lora", "training", "evaluation"}


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML experiment config and reject incomplete baselines."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Experiment config must be a YAML mapping")
    missing = REQUIRED_SECTIONS - config.keys()
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(sorted(missing))}")
    if config["model"].get("source_language") == config["model"].get("target_language"):
        raise ValueError("Source and target languages must differ")
    return config

