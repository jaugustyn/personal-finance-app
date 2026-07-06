"""Shared schema metadata for custom transaction imports."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportFieldSpec:
    key: str
    required: bool = False
    recommended: bool = False
    description: str = ""


IMPORT_FIELD_SPECS: tuple[ImportFieldSpec, ...] = (
    ImportFieldSpec("date", required=True, description="Booking/transaction date."),
    ImportFieldSpec("amount", required=True, description="Signed transaction amount."),
    ImportFieldSpec("currency", description="Currency code; defaults to PLN."),
    ImportFieldSpec(
        "merchant",
        required=True,
        description="Merchant or counterparty; improves deduplication and ML.",
    ),
    ImportFieldSpec(
        "title",
        recommended=True,
        description="Payment title, memo or description; improves ML.",
    ),
    ImportFieldSpec("category", description="Original bank/source category."),
    ImportFieldSpec("external_id", description="Bank/source transaction id."),
)

IMPORT_FIELD_KEYS = frozenset(spec.key for spec in IMPORT_FIELD_SPECS)
REQUIRED_IMPORT_FIELDS = frozenset(
    spec.key for spec in IMPORT_FIELD_SPECS if spec.required
)
RECOMMENDED_IMPORT_FIELDS = frozenset(
    spec.key for spec in IMPORT_FIELD_SPECS if spec.recommended
)


def import_field_specs_payload() -> list[dict[str, object]]:
    return [
        {
            "key": spec.key,
            "required": spec.required,
            "recommended": spec.recommended,
            "description": spec.description,
        }
        for spec in IMPORT_FIELD_SPECS
    ]


def clean_column_map(mapping: Mapping[str, object]) -> dict[str, str]:
    """Keep supported non-empty logical fields from a user-provided mapping."""
    cleaned: dict[str, str] = {}
    for key, value in mapping.items():
        if key not in IMPORT_FIELD_KEYS:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned[key] = text
    return cleaned


def validate_column_map(
    mapping: dict[str, str],
    *,
    headers: list[str] | None = None,
) -> list[str]:
    """Return validation errors for custom import mapping."""
    errors: list[str] = []
    for key in sorted(REQUIRED_IMPORT_FIELDS):
        if not mapping.get(key):
            errors.append(f"Missing required column mapping: {key}")
    if headers is not None:
        known = set(headers)
        for key, column in sorted(mapping.items()):
            if column not in known:
                errors.append(f"Mapped column for {key!r} does not exist: {column!r}")
    return errors


def import_quality_warnings(mapping: dict[str, str]) -> list[str]:
    """Warnings for imports that can run but will produce lower-quality analytics."""
    warnings: list[str] = []
    if not mapping.get("currency"):
        warnings.append("Currency is optional; missing values will default to PLN.")
    return warnings
