from src.corpus.config import load_config


def test_config_loads():
    config = load_config()
    assert config.ocr_dpi == 400
    assert config.input_dir.name == "input"
    assert config.output_dir.name == "exports"
