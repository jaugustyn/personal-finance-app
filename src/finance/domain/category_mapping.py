"""Map source-native category labels to the unified expense-category schema.

The unified schema is intentionally compact because the labelled training set
is small. Bank/source labels with no clear expense-category mapping (e.g.
"Inne", "Bez kategorii", "Wynagrodzenie", "income", "transfer") are returned
as ``None`` — those rows are excluded from supervised category training and
remain available for EDA / unsupervised analyses.
"""
from __future__ import annotations

from finance.domain.enums import Category
from finance.transactions.system_rules import RuleDecision, system_rules_registry


def _category(value: str | None) -> Category | None:
    return Category(value) if value is not None else None


# Pekao SA "Kategoria" column → unified Category (or None to skip).
PEKAO_CATEGORY_MAP: dict[str, Category | None] = {
    key: _category(value)
    for key, value in system_rules_registry().pekao_category_map.items()
}


def map_pekao_category(raw: str | None) -> Category | None:
    return _category(explain_pekao_category(raw).result)


_SOURCE_CATEGORY_MAP: dict[str, Category | None] = {
    key: _category(value)
    for key, value in system_rules_registry().source_category_map.items()
}


def explain_pekao_category(raw: str | None) -> RuleDecision:
    return system_rules_registry().explain_pekao_category(raw)


def explain_source_category(raw: str | None) -> RuleDecision:
    return system_rules_registry().explain_source_category(raw)


def map_source_category(raw: str | None) -> Category | None:
    """Map a bank/generic/source category label to the ML expense category."""
    return _category(explain_source_category(raw).result)


# --- Two-level taxonomy ----------------------------------------------------
#
# The :class:`Category` values are the *parent groups* and remain the single ML
# target — the classifier keeps predicting groups, so training labels, macro-F1
# and the confusion matrix stay at the stable group level.
#
# Subcategories are an optional, user-facing *refinement* layer stored in a
# separate ``Transaction.subcategory`` column. They are assigned by personal
# rules or manual review and are never predicted, so they cannot leak into or
# degrade the supervised model. Slugs are bank-agnostic ``lower_snake_case``
# and globally unique, so they coexist with the parent groups in the same
# ``categories`` catalog table.

# Display/swatch color per parent group (shared by API seeding and migration).
SYSTEM_CATEGORY_COLORS: dict[Category, str] = {
    Category.FOOD: "#f59e0b",
    Category.TRANSPORT: "#3b82f6",
    Category.SUBSCRIPTIONS: "#a855f7",
    Category.HEALTH: "#ef4444",
    Category.ENTERTAINMENT: "#ec4899",
    Category.HOUSING: "#10b981",
    Category.SAVINGS: "#14b8a6",
    Category.SHOPPING: "#6366f1",
    Category.OTHER: "#6b7280",
}

SYSTEM_SUBCATEGORIES: dict[Category, tuple[str, ...]] = {
    Category.FOOD: ("groceries", "dining_out", "fast_food", "alcohol"),
    Category.TRANSPORT: ("fuel", "public_transport", "taxi", "parking", "vehicle"),
    Category.SUBSCRIPTIONS: (
        "streaming",
        "software",
        "telecom",
        "gym_membership",
    ),
    Category.HEALTH: ("pharmacy", "doctor", "dental", "health_insurance"),
    Category.ENTERTAINMENT: ("events", "games", "hobbies", "books_media", "sports"),
    Category.HOUSING: ("rent", "mortgage", "utilities", "internet", "repairs"),
    Category.SAVINGS: ("deposit", "investment", "retirement", "emergency_fund"),
    Category.SHOPPING: (
        "online_retail",
        "clothing",
        "electronics",
        "personal_goods",
    ),
    Category.OTHER: ("fees", "taxes", "gifts", "charity", "misc"),
}


def subcategory_parent(name: str | None) -> Category | None:
    """Return the parent group of a system subcategory, or ``None`` if unknown."""
    if not name:
        return None
    for parent, subs in SYSTEM_SUBCATEGORIES.items():
        if name in subs:
            return parent
    return None


def subcategory_parent_value(name: str | None) -> str | None:
    """Return the string parent for a system subcategory."""
    parent = subcategory_parent(name)
    return parent.value if parent is not None else None


def subcategory_belongs_to(subcategory: str | None, category: str | None) -> bool:
    """Check whether a system subcategory belongs to a parent category."""
    if not subcategory or not category:
        return False
    return subcategory_parent_value(subcategory) == category
