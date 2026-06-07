from __future__ import annotations

import copy
import json
from importlib import resources

import pytest

from finance.transactions.system_rules import (
    RULES_RESOURCE,
    SystemRulesError,
    build_registry,
    system_rules_registry,
)


def _raw_rules() -> dict:
    text = (
        resources.files("finance.transactions")
        .joinpath(RULES_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


def test_bundled_system_rules_validate_and_have_stable_order() -> None:
    registry = system_rules_registry()
    priorities = [rule.priority for rule in registry.transaction_type_rules]
    ids = [rule.id for rule in registry.transaction_type_rules]

    assert priorities == sorted(priorities)
    assert len(ids) == len(set(ids))
    assert registry.category_suggestion_candidate_types == frozenset(
        {"purchase", "bank_fee", "savings_investment", "other"}
    )
    assert registry.explain_source_category("Travel").result == "transport"
    assert registry.explain_source_category("Serwis samochodowy").result == "transport"
    assert registry.explain_source_category("Wynagrodzenie").result is None
    assert dict(registry.llm_category_aliases)["zakupy"] == "shopping"


def test_registry_rejects_duplicate_rule_ids() -> None:
    data = copy.deepcopy(_raw_rules())
    data["transaction_type_rules"][1]["id"] = data["transaction_type_rules"][0]["id"]

    with pytest.raises(SystemRulesError, match="Duplicate transaction rule id"):
        build_registry(data)


def test_registry_rejects_duplicate_priorities() -> None:
    data = copy.deepcopy(_raw_rules())
    data["transaction_type_rules"][1]["priority"] = data["transaction_type_rules"][0][
        "priority"
    ]

    with pytest.raises(SystemRulesError, match="Duplicate transaction rule priority"):
        build_registry(data)


def test_registry_rejects_invalid_enums_and_empty_matchers() -> None:
    invalid_enum = copy.deepcopy(_raw_rules())
    invalid_enum["transaction_type_rules"][0]["result"] = "not_a_type"
    with pytest.raises(SystemRulesError, match="invalid transaction type"):
        build_registry(invalid_enum)

    empty_matcher = copy.deepcopy(_raw_rules())
    empty_matcher["transaction_type_rules"][0]["keywords"] = []
    empty_matcher["transaction_type_rules"][0]["regexes"] = []
    with pytest.raises(SystemRulesError, match="must define keywords or regexes"):
        build_registry(empty_matcher)
