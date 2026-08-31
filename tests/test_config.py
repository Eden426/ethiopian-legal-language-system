from pathlib import Path

from src.common.config import load_config


def test_baseline_config_is_structurally_valid() -> None:
    config = load_config(Path("configs/amh_eng_lora.yaml"))
    assert config["model"]["source_language"] == "amh_Ethi"
    assert config["model"]["target_language"] == "eng_Latn"
    assert config["training"]["train_batch_size"] == 1
    assert config["evaluation"]["primary_metric"] == "chrf"

