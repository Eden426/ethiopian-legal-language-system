from src.corpus.alignment.aligner import align_paragraphs


def test_index_alignment_preserves_unmatched_items():
    result = align_paragraphs(["am1", "am2"], ["en1"])
    assert result == [
        {"amharic": "am1", "english": "en1"},
        {"amharic": "am2", "english": ""},
    ]
