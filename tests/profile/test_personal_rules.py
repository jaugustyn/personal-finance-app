"""Tests for personal rule matching and normalization."""
from __future__ import annotations

from finance.profile.service import create_rule, effect_for_transaction
from finance.transactions.normalization import normalize_merchant


def test_normalize_merchant_removes_accents_and_noise() -> None:
    assert normalize_merchant("  ŻABKA #123 / Kraków  ") == "zabka 123 krakow"


def test_effect_for_transaction_uses_priority(db_session) -> None:
    create_rule(db_session, pattern="zabka", category="other", priority=100)
    preferred = create_rule(db_session, pattern="żabka", category="food", priority=10)

    effect = effect_for_transaction(db_session, merchant="ŻABKA 123", title="Zakupy")

    assert effect is not None
    assert effect.rule.id == preferred.id
    assert effect.category == "food"
