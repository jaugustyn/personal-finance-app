"""Map bank-native category labels to the unified 8-class schema.

The unified schema is intentionally small (8 classes) because the labelled
training set is small. Bank-native labels with no clear mapping (e.g. "Inne",
"Bez kategorii", "Wynagrodzenie") are returned as None — those rows are
excluded from supervised training and remain available for EDA / unsupervised
analyses.
"""
from __future__ import annotations

from finance.domain.enums import Category

# Pekao SA "Kategoria" column → unified Category (or None to skip).
PEKAO_CATEGORY_MAP: dict[str, Category | None] = {
    # food
    "Artykuły spożywcze": Category.FOOD,
    "Restauracje i kawiarnie": Category.FOOD,
    # transport
    "Paliwo": Category.TRANSPORT,
    "Transport publiczny": Category.TRANSPORT,
    # subscriptions
    "Internet, TV, telefon": Category.SUBSCRIPTIONS,
    # health
    "Opieka medyczna": Category.HEALTH,
    # entertainment
    "Kino i teatr": Category.ENTERTAINMENT,
    "Hobby": Category.ENTERTAINMENT,
    "Książki": Category.ENTERTAINMENT,
    "Komputer, konsola": Category.ENTERTAINMENT,
    # housing
    "Wyposażenie": Category.HOUSING,
    "Sprzęt AGD i RTV": Category.HOUSING,
    # savings — interest income / investment returns
    "Odsetki, zwrot z inwestycji": Category.SAVINGS,
    # other (mapped explicitly, kept for transparency)
    "Kosmetyki": Category.OTHER,
    "Ubrania": Category.OTHER,
    "Zakupy przez internet": Category.OTHER,
    "Czesne, opłaty organizacyjne": Category.OTHER,
    "Opłaty bankowe": Category.OTHER,
    "Podatki": Category.OTHER,
    # ambiguous / unlabelled — leave as None so training skips them
    "Inne": None,
    "Bez kategorii": None,
    "Sprzedaż": None,  # often incoming personal transfers
    "Wynagrodzenie": None,
    "Wypłata z rachunku": None,
}


def map_pekao_category(raw: str | None) -> Category | None:
    if raw is None:
        return None
    return PEKAO_CATEGORY_MAP.get(raw.strip())
