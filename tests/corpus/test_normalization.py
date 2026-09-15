from src.corpus.normalization.text import (
    clean_text,
    is_valid_amharic_line,
    recover_ethiopic_numerals,
)


def test_clean_text_keeps_amharic_and_english():
    result = clean_text("ሰላም Hello @#$")
    assert "ሰላም" in result
    assert "Hello" in result
    assert "@" not in result


def test_recover_ethiopic_numerals():
    assert recover_ethiopic_numerals("1 2 3") == "፩ ፪ ፫"


def test_amharic_validation():
    assert is_valid_amharic_line("ይህ የሕግ አንቀጽ ነው።")
    assert not is_valid_amharic_line("English only line")
