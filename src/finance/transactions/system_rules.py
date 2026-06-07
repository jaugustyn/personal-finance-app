"""Config-backed system rules for transaction metadata and category aliases."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.transactions.normalization import normalize_text

RULES_RESOURCE = "system_rules.json"


class SystemRulesError(ValueError):
    """Raised when the bundled system-rules registry is invalid."""


@dataclass(frozen=True)
class RuleDecision:
    """Traceable decision returned by the system-rule registry."""

    result: str | None
    rule_id: str
    reason: str
    matched: str | None = None


@dataclass(frozen=True)
class TransactionTypeRule:
    id: str
    priority: int
    result: str
    reason: str
    direction: str | None
    keywords: tuple[str, ...]
    regexes: tuple[re.Pattern[str], ...]
    special: str | None = None


@dataclass(frozen=True)
class SystemRulesRegistry:
    version: int
    category_suggestion_candidate_types: frozenset[str]
    rule_categories_by_type: dict[str, str]
    transaction_type_rules: tuple[TransactionTypeRule, ...]
    person_transfer_patterns: tuple[re.Pattern[str], ...]
    person_transfer_exclusions: tuple[str, ...]
    person_transfer_source_categories: frozenset[str]
    person_refund_keywords: tuple[str, ...]
    business_counterparty_terms: frozenset[str]
    pekao_category_map: dict[str, str | None]
    source_category_map: dict[str, str | None]
    llm_category_aliases: tuple[tuple[str, str], ...]

    def category_for_transaction_type(self, transaction_type: TransactionType) -> str | None:
        return self.rule_categories_by_type.get(transaction_type.value)

    def explain_pekao_category(self, raw: str | None) -> RuleDecision:
        if raw is None:
            return RuleDecision(None, "source.pekao.empty", "No raw category.")
        stripped = raw.strip()
        if stripped in self.pekao_category_map:
            result = self.pekao_category_map[stripped]
            return RuleDecision(
                result,
                f"source.pekao.{normalize_text(stripped) or 'empty'}",
                "Exact Pekao source-category mapping.",
                stripped,
            )
        return RuleDecision(None, "source.pekao.no_match", "No Pekao mapping.", stripped)

    def explain_source_category(self, raw: str | None) -> RuleDecision:
        if raw is None:
            return RuleDecision(None, "source.generic.empty", "No raw category.")
        pekao = self.explain_pekao_category(raw)
        if pekao.rule_id != "source.pekao.no_match":
            return pekao
        stripped = raw.strip()
        norm = normalize_text(stripped)
        if norm in self.source_category_map:
            result = self.source_category_map[norm]
            return RuleDecision(
                result,
                f"source.generic.{norm or 'empty'}",
                "Generic source-category mapping.",
                stripped,
            )
        return RuleDecision(None, "source.generic.no_match", "No source-category mapping.", stripped)


def _as_dict(data: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SystemRulesError(f"{path} must be an object.")
    return data


def _as_list(data: Any, *, path: str) -> list[Any]:
    if not isinstance(data, list):
        raise SystemRulesError(f"{path} must be a list.")
    return data


def _string_list(data: Any, *, path: str, allow_empty: bool = False) -> tuple[str, ...]:
    values: list[str] = []
    for index, item in enumerate(_as_list(data or [], path=path)):
        if not isinstance(item, str):
            raise SystemRulesError(f"{path}[{index}] must be a string.")
        value = item.strip()
        if not value and not allow_empty:
            raise SystemRulesError(f"{path}[{index}] cannot be empty.")
        values.append(value)
    return tuple(values)


def _transaction_type(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        raise SystemRulesError(f"{path} must be a transaction type string.")
    try:
        return TransactionType(value).value
    except ValueError as exc:
        raise SystemRulesError(f"{path} has invalid transaction type: {value!r}.") from exc


def _category(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SystemRulesError(f"{path} must be a category string or null.")
    try:
        return Category(value).value
    except ValueError as exc:
        raise SystemRulesError(f"{path} has invalid category: {value!r}.") from exc


def _direction(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SystemRulesError(f"{path} must be a transaction direction string.")
    try:
        return TransactionDirection(value).value
    except ValueError as exc:
        raise SystemRulesError(f"{path} has invalid direction: {value!r}.") from exc


def _compile_patterns(data: Any, *, path: str) -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    for index, pattern in enumerate(_string_list(data or [], path=path)):
        try:
            patterns.append(re.compile(pattern, re.I))
        except re.error as exc:
            raise SystemRulesError(f"{path}[{index}] has invalid regex: {pattern!r}.") from exc
    return tuple(patterns)


def _category_map(data: Any, *, path: str, normalize_keys: bool) -> dict[str, str | None]:
    raw = _as_dict(data, path=path)
    out: dict[str, str | None] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise SystemRulesError(f"{path} contains an empty/non-string key.")
        out_key = normalize_text(key) if normalize_keys else key.strip()
        out[out_key] = _category(value, path=f"{path}.{key}")
    return out


def _candidate_types(data: Any) -> frozenset[str]:
    values = {_transaction_type(item, path="category_suggestion_candidate_types") for item in data}
    if not values:
        raise SystemRulesError("category_suggestion_candidate_types cannot be empty.")
    return frozenset(values)


def _transaction_rules(data: Any) -> tuple[TransactionTypeRule, ...]:
    rules: list[TransactionTypeRule] = []
    seen_ids: set[str] = set()
    seen_priorities: set[int] = set()
    for index, raw_rule in enumerate(_as_list(data, path="transaction_type_rules")):
        rule = _as_dict(raw_rule, path=f"transaction_type_rules[{index}]")
        raw_id = rule.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise SystemRulesError(f"transaction_type_rules[{index}].id cannot be empty.")
        rule_id = raw_id.strip()
        if rule_id in seen_ids:
            raise SystemRulesError(f"Duplicate transaction rule id: {rule_id}.")
        seen_ids.add(rule_id)
        priority = rule.get("priority")
        if not isinstance(priority, int):
            raise SystemRulesError(f"{rule_id}.priority must be an integer.")
        if priority in seen_priorities:
            raise SystemRulesError(f"Duplicate transaction rule priority: {priority}.")
        seen_priorities.add(priority)
        result = _transaction_type(rule.get("result"), path=f"{rule_id}.result")
        direction = _direction(rule.get("direction"), path=f"{rule_id}.direction")
        keywords = _string_list(rule.get("keywords", []), path=f"{rule_id}.keywords")
        regexes = _compile_patterns(rule.get("regexes", []), path=f"{rule_id}.regexes")
        special = rule.get("special")
        if special is not None and special != "person_transfer":
            raise SystemRulesError(f"{rule_id}.special has unsupported value: {special!r}.")
        if special == "person_transfer" and result != TransactionType.PERSON_TRANSFER.value:
            raise SystemRulesError(f"{rule_id}.special=person_transfer must return person_transfer.")
        if special is None and not keywords and not regexes:
            raise SystemRulesError(f"{rule_id} must define keywords or regexes.")
        reason = rule.get("reason") if isinstance(rule.get("reason"), str) else ""
        rules.append(
            TransactionTypeRule(
                id=rule_id,
                priority=priority,
                result=result,
                reason=reason.strip() or "System transaction-type rule.",
                direction=direction,
                keywords=keywords,
                regexes=regexes,
                special=special,
            )
        )
    if not rules:
        raise SystemRulesError("transaction_type_rules cannot be empty.")
    return tuple(sorted(rules, key=lambda item: item.priority))


def _rule_categories_by_type(data: Any) -> dict[str, str]:
    raw = _as_dict(data, path="rule_categories_by_type")
    out: dict[str, str] = {}
    for key, value in raw.items():
        tx_type = _transaction_type(key, path="rule_categories_by_type.key")
        category = _category(value, path=f"rule_categories_by_type.{key}")
        if category is None:
            raise SystemRulesError(f"rule_categories_by_type.{key} cannot be null.")
        out[tx_type] = category
    return out


def _llm_aliases(data: Any) -> tuple[tuple[str, str], ...]:
    aliases: list[tuple[str, str]] = []
    for index, item in enumerate(_as_list(data, path="llm_category_aliases")):
        raw = _as_dict(item, path=f"llm_category_aliases[{index}]")
        alias = raw.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            raise SystemRulesError(f"llm_category_aliases[{index}].alias cannot be empty.")
        category = _category(raw.get("category"), path=f"llm_category_aliases[{index}].category")
        if category is None:
            raise SystemRulesError(f"llm_category_aliases[{index}].category cannot be null.")
        aliases.append((alias.strip(), category))
    return tuple(aliases)


def build_registry(data: dict[str, Any]) -> SystemRulesRegistry:
    """Validate raw JSON-compatible data and build a registry."""
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise SystemRulesError("version must be a positive integer.")
    person = _as_dict(data.get("person_transfer"), path="person_transfer")
    return SystemRulesRegistry(
        version=version,
        category_suggestion_candidate_types=_candidate_types(
            _as_list(
                data.get("category_suggestion_candidate_types"),
                path="category_suggestion_candidate_types",
            )
        ),
        rule_categories_by_type=_rule_categories_by_type(data.get("rule_categories_by_type")),
        transaction_type_rules=_transaction_rules(data.get("transaction_type_rules")),
        person_transfer_patterns=_compile_patterns(
            person.get("patterns", []),
            path="person_transfer.patterns",
        ),
        person_transfer_exclusions=_string_list(
            person.get("expense_exclusion_keywords", []),
            path="person_transfer.expense_exclusion_keywords",
        ),
        person_transfer_source_categories=frozenset(
            normalize_text(value)
            for value in _string_list(
                person.get("source_categories", []),
                path="person_transfer.source_categories",
            )
        ),
        person_refund_keywords=_string_list(
            person.get("person_refund_keywords", []),
            path="person_transfer.person_refund_keywords",
        ),
        business_counterparty_terms=frozenset(
            normalize_text(value)
            for value in _string_list(
                person.get("business_counterparty_terms", []),
                path="person_transfer.business_counterparty_terms",
            )
        ),
        pekao_category_map=_category_map(
            data.get("pekao_category_map"),
            path="pekao_category_map",
            normalize_keys=False,
        ),
        source_category_map=_category_map(
            data.get("source_category_map"),
            path="source_category_map",
            normalize_keys=True,
        ),
        llm_category_aliases=_llm_aliases(data.get("llm_category_aliases")),
    )


@lru_cache(maxsize=1)
def system_rules_registry() -> SystemRulesRegistry:
    """Load and validate the bundled system-rule registry."""
    raw = (
        resources.files("finance.transactions")
        .joinpath(RULES_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return build_registry(json.loads(raw))
