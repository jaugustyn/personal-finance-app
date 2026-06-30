"""Personalization service for profile settings and transaction rules."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import CATEGORY_VALUES, TRANSACTION_TYPE_VALUES
from finance.domain.models import PersonalRule, UserProfile
from finance.transactions.normalization import normalize_text

PROFILE_ID = 1
RULE_MODE_SUGGEST = "suggest_only"
RULE_MODE_AUTO = "auto_apply"
RULE_TARGETS = {"merchant", "title", "both"}
RULE_MODES = {RULE_MODE_SUGGEST, RULE_MODE_AUTO}


@dataclass(frozen=True)
class RuleEffect:
    rule: PersonalRule
    category: str | None
    transaction_type: str | None
    is_transfer: bool | None
    mode: str
    confidence: float


def get_or_create_profile(session: Session) -> UserProfile:
    profile = session.get(UserProfile, PROFILE_ID)
    if profile is not None:
        return profile
    profile = UserProfile(id=PROFILE_ID)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(
    session: Session,
    *,
    base_currency: str | None = None,
    salary_day: int | None = None,
    monthly_savings_goal: Decimal | None = None,
    category_limits: dict[str, float] | None = None,
) -> UserProfile:
    profile = get_or_create_profile(session)
    if base_currency is not None:
        profile.base_currency = base_currency.strip().upper()[:3] or "PLN"
    profile.salary_day = salary_day
    profile.monthly_savings_goal = monthly_savings_goal
    if category_limits is not None:
        profile.category_limits = _clean_category_limits(category_limits)
    session.commit()
    session.refresh(profile)
    return profile


def _clean_category_limits(raw: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for category, value in raw.items():
        key = str(category).strip().lower()
        if key not in CATEGORY_VALUES:
            continue
        numeric = float(value)
        if numeric >= 0:
            out[key] = numeric
    return out


def _validate_rule_payload(
    *,
    pattern: str,
    pattern_target: str,
    category: str | None,
    transaction_type: str | None,
    mode: str,
    confidence: float,
) -> None:
    if not normalize_text(pattern):
        raise ValueError("Rule pattern cannot be empty.")
    if pattern_target not in RULE_TARGETS:
        raise ValueError(f"Invalid rule target: {pattern_target}.")
    if mode not in RULE_MODES:
        raise ValueError(f"Invalid rule mode: {mode}.")
    if category is not None and category not in CATEGORY_VALUES:
        raise ValueError(f"Invalid category: {category}.")
    if transaction_type is not None and transaction_type not in TRANSACTION_TYPE_VALUES:
        raise ValueError(f"Invalid transaction type: {transaction_type}.")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Rule confidence must be between 0 and 1.")


def create_rule(
    session: Session,
    *,
    pattern: str,
    pattern_target: str = "merchant",
    category: str | None = None,
    transaction_type: str | None = None,
    is_transfer: bool | None = None,
    priority: int = 100,
    active: bool = True,
    mode: str = RULE_MODE_SUGGEST,
    confidence: float = 0.95,
) -> PersonalRule:
    _validate_rule_payload(
        pattern=pattern,
        pattern_target=pattern_target,
        category=category,
        transaction_type=transaction_type,
        mode=mode,
        confidence=confidence,
    )
    rule = PersonalRule(
        pattern=pattern.strip(),
        pattern_norm=normalize_text(pattern),
        pattern_target=pattern_target,
        category=category,
        transaction_type=transaction_type,
        is_transfer=is_transfer,
        priority=priority,
        active=active,
        mode=mode,
        confidence=confidence,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def update_rule(session: Session, rule_id: int, **changes: Any) -> PersonalRule | None:
    rule = session.get(PersonalRule, rule_id)
    if rule is None:
        return None
    pattern = str(changes.get("pattern", rule.pattern))
    pattern_target = str(changes.get("pattern_target", rule.pattern_target))
    category = changes.get("category", rule.category)
    transaction_type = changes.get("transaction_type", rule.transaction_type)
    mode = str(changes.get("mode", rule.mode))
    confidence = float(changes.get("confidence", rule.confidence))
    _validate_rule_payload(
        pattern=pattern,
        pattern_target=pattern_target,
        category=category,
        transaction_type=transaction_type,
        mode=mode,
        confidence=confidence,
    )
    rule.pattern = pattern.strip()
    rule.pattern_norm = normalize_text(pattern)
    rule.pattern_target = pattern_target
    rule.category = category
    rule.transaction_type = transaction_type
    rule.is_transfer = changes.get("is_transfer", rule.is_transfer)
    rule.priority = int(changes.get("priority", rule.priority))
    rule.active = bool(changes.get("active", rule.active))
    rule.mode = mode
    rule.confidence = confidence
    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(PersonalRule, rule_id)
    if rule is None:
        return False
    session.delete(rule)
    session.commit()
    return True


def list_rules(session: Session, *, active_only: bool = False) -> list[PersonalRule]:
    stmt = select(PersonalRule).order_by(PersonalRule.priority.asc(), PersonalRule.id.asc())
    if active_only:
        stmt = stmt.where(PersonalRule.active.is_(True))
    return list(session.execute(stmt).scalars().all())


def find_matching_rule(
    session: Session,
    *,
    merchant: str | None,
    title: str | None,
) -> PersonalRule | None:
    merchant_norm = normalize_text(merchant)
    title_norm = normalize_text(title)
    for rule in list_rules(session, active_only=True):
        if _matches(rule, merchant_norm=merchant_norm, title_norm=title_norm):
            return rule
    return None


def effect_for_transaction(
    session: Session,
    *,
    merchant: str | None,
    title: str | None,
) -> RuleEffect | None:
    rule = find_matching_rule(session, merchant=merchant, title=title)
    if rule is None:
        return None
    return RuleEffect(
        rule=rule,
        category=rule.category,
        transaction_type=rule.transaction_type,
        is_transfer=rule.is_transfer,
        mode=rule.mode,
        confidence=float(rule.confidence),
    )


def remember_merchant_category(
    session: Session,
    *,
    merchant: str,
    category: str,
) -> PersonalRule | None:
    pattern_norm = normalize_text(merchant)
    if not pattern_norm:
        return None
    existing = session.execute(
        select(PersonalRule)
        .where(PersonalRule.pattern_norm == pattern_norm)
        .where(PersonalRule.pattern_target == "merchant")
        .where(PersonalRule.category == category)
    ).scalar_one_or_none()
    if existing is not None:
        existing.active = True
        session.commit()
        session.refresh(existing)
        return existing
    return create_rule(
        session,
        pattern=merchant,
        pattern_target="merchant",
        category=category,
        mode=RULE_MODE_SUGGEST,
        confidence=0.95,
    )


def _matches(rule: PersonalRule, *, merchant_norm: str, title_norm: str) -> bool:
    pattern = normalize_text(rule.pattern_norm or rule.pattern)
    if not pattern:
        return False
    if rule.pattern_target == "merchant":
        return pattern in merchant_norm
    if rule.pattern_target == "title":
        return pattern in title_norm
    return pattern in f"{merchant_norm} {title_norm}".strip()
