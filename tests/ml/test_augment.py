"""Unit tests for the augmentation post-processing logic (no Ollama needed)."""
from finance.ml.classification.augment import _build_prompt, _parse_lines


def test_parse_lines_strips_bullets_and_preamble() -> None:
    raw = """Oto 5 realistycznych opisów dla kategorii "health":

1. APTEKA DR.MAX KRAKOW
2) MEDICOVER WARSZAWA wizyta
- LUX MED diagnostyka
* DOZ APTEKA Floriańska
"NZOZ Centrum Zdrowia"
Poniżej lista:
"""
    out = _parse_lines(raw)
    assert "APTEKA DR.MAX KRAKOW" in out
    assert "MEDICOVER WARSZAWA wizyta" in out
    assert "LUX MED diagnostyka" in out
    assert "DOZ APTEKA Floriańska" in out
    assert "NZOZ Centrum Zdrowia" in out
    assert all("oto " not in s.lower() for s in out)
    assert all(not s.endswith(":") for s in out)
    assert all(not s.lower().startswith("poniżej") for s in out)


def test_parse_lines_drops_llm_meta_lines_from_generated_csv() -> None:
    raw = """Oto 5 realistycznych opisów transakcji dla kategorii "housing":
1.LEROY MERLIN Bielany
2- IKEA KRAKOW terminal POS
Przykłady dla kategorii "housing":
CASTORAMA wyposażenie
"""
    out = _parse_lines(raw)
    assert out == [
        "LEROY MERLIN Bielany",
        "IKEA KRAKOW terminal POS",
        "CASTORAMA wyposażenie",
    ]


def test_build_prompt_mentions_count_and_category() -> None:
    p = _build_prompt("health", 7)
    assert "DOKŁADNIE 7" in p
    assert '"health"' in p
    assert "APTEKA" in p  # seed example included
