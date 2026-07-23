"""UTF-8 / mojibake repair helpers."""

from utils.text_encoding import ensure_utf8_text, looks_mojibake, repair_mojibake


def test_repair_arabic_mojibake():
    arabic = "عبد الباسط هارون جبريل"
    broken = arabic.encode("utf-8").decode("latin-1")
    assert looks_mojibake(broken)
    assert repair_mojibake(broken) == arabic
    assert ensure_utf8_text(broken) == arabic


def test_repair_smart_apostrophe_mojibake():
    text = "Firebreak's platform"
    broken = text.encode("utf-8").decode("latin-1")
    assert repair_mojibake(broken) == text
