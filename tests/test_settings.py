from pathlib import Path

import pytest
from pydantic import ValidationError

from src.common.settings import load_app_settings


def test_settings_use_safe_local_defaults() -> None:
    settings = load_app_settings({})

    assert settings.data_path == Path("data/processed")
    assert settings.database_url.startswith("sqlite:///")
    assert settings.model_id == "facebook/nllb-200-distilled-600M"


def test_settings_read_prefixed_environment_values() -> None:
    settings = load_app_settings({"ELLS_DATA_PATH": "local/private-data"})

    assert settings.data_path == Path("local/private-data")


def test_settings_reject_empty_model_id() -> None:
    with pytest.raises(ValidationError, match="setting must not be empty"):
        load_app_settings({"ELLS_MODEL_ID": " "})
