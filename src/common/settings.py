"""Environment-based settings for the local MVP."""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


class AppSettings(BaseModel):
    """Validated runtime settings without reading private data during import."""

    model_config = ConfigDict(frozen=True)

    api_url: str = "http://127.0.0.1:8000"
    model_id: str = "facebook/nllb-200-distilled-600M"
    model_revision: str = "replace-with-immutable-revision"
    data_path: Path = Path("data/processed")
    database_url: str = "sqlite:///./data/ells.db"

    @field_validator("api_url", "model_id", "model_revision", "database_url")
    @classmethod
    def reject_empty_values(cls, value: str) -> str:
        """Reject empty settings early with an actionable error."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("setting must not be empty")
        return cleaned


def load_app_settings(environ: dict[str, str] | None = None) -> AppSettings:
    """Load MVP settings from ELLS-prefixed environment variables."""

    source = os.environ if environ is None else environ
    values = {
        "api_url": source.get("ELLS_API_URL", AppSettings.model_fields["api_url"].default),
        "model_id": source.get("ELLS_MODEL_ID", AppSettings.model_fields["model_id"].default),
        "model_revision": source.get(
            "ELLS_MODEL_REVISION", AppSettings.model_fields["model_revision"].default
        ),
        "data_path": source.get(
            "ELLS_DATA_PATH", str(AppSettings.model_fields["data_path"].default)
        ),
        "database_url": source.get(
            "ELLS_DATABASE_URL", AppSettings.model_fields["database_url"].default
        ),
    }
    return AppSettings.model_validate(values)
