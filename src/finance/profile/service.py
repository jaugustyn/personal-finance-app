"""Personalization service for profile settings and transaction rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import TRANSACTION_TYPE_VALUES
from finance.domain.models import CategoryDef, PersonalRule, UserProfile
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


@dataclass(frozen=True)
class PersonalRuleMatcher:
    """Request-scoped matcher backed by one active-rules query."""

    rules: tuple[PersonalRule, ...]

    def find(self, *, merchant: str | None, title: str | None) -> PersonalRule | None:
        merchant_norm = normalize_text(merchant)
        title_norm = normalize_text(title)
        for rule in self.rules:
            if _matches(rule, merchant_norm=merchant_norm, title_norm=title_norm):
                return rule
        return None

    def effect(self, *, merchant: str | None, title: str | None) -> RuleEffect | None:
        rule = self.find(merchant=merchant, title=title)
        return _effect_for_rule(rule) if rule is not None else None


def get_profile(session: Session) -> UserProfile | None:
    """Return the singleton profile without creating state during a read."""
    return session.get(UserProfile, PROFILE_ID)


def get_or_create_profile(session: Session) -> UserProfile:
    """Return the singleton profile, flushing a new row without committing it."""
    profile = get_profile(session)
    if profile is not None:
        return profile
    profile = UserProfile(id=PROFILE_ID)
    session.add(profile)
    session.flush()
    return profile


def is_assistant_llm_enabled(session: Session) -> bool:
    """Return the user preference without creating profile state during a read."""
    profile = get_profile(session)
    return profile is None or profile.assistant_llm_enabled


def get_assistant_llm_model(session: Session) -> str | None:
    """Return the optional assistant-specific Ollama model override."""
    profile = get_profile(session)
    return profile.assistant_llm_model if profile is not None else None


def set_assistant_llm_preferences(
    session: Session,
    *,
    enabled: bool,
    model: str | None = None,
) -> UserProfile:
    """Persist local-model preferences for the single-user assistant."""
    profile = get_or_create_profile(session)
    profile.assistant_llm_enabled = enabled
    if model is not None:
        normalized_model = model.strip()
        if not normalized_model or len(normalized_model) > 255:
            raise ValueError("Invalid Ollama model name.")
        profile.assistant_llm_model = normalized_model
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return profile


def set_assistant_llm_enabled(session: Session, *, enabled: bool) -> bool:
    """Persist the enable switch while retaining the selected model."""
    return set_assistant_llm_preferences(session, enabled=enabled).assistant_llm_enabled


def _validate_rule_payload(
    session: Session,
    *,
    pattern: str,
    pattern_target: str,
    category: str | None,
    transaction_type: str | None,
    mode: str,
    confidence: float,
) -> str | None:
    if not normalize_text(pattern):
        raise ValueError("Rule pattern cannot be empty.")
    if pattern_target not in RULE_TARGETS:
        raise ValueError(f"Invalid rule target: {pattern_target}.")
    if mode not in RULE_MODES:
        raise ValueError(f"Invalid rule mode: {mode}.")
    normalized_category = category.strip().lower() if category is not None else None
    if normalized_category is not None and session.scalar(
        select(CategoryDef.id).where(CategoryDef.name == normalized_category)
    ) is None:
        raise ValueError(f"Invalid category: {category}.")
    if transaction_type is not None and transaction_type not in TRANSACTION_TYPE_VALUES:
        raise ValueError(f"Invalid transaction type: {transaction_type}.")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Rule confidence must be between 0 and 1.")
    return normalized_category


def _add_rule(
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
    category = _validate_rule_payload(
        session,
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
    session.flush()
    return rule


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
    """Create a rule as a top-level command."""
    try:
        rule = _add_rule(
            session,
            pattern=pattern,
            pattern_target=pattern_target,
            category=category,
            transaction_type=transaction_type,
            is_transfer=is_transfer,
            priority=priority,
            active=active,
            mode=mode,
            confidence=confidence,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
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
    category = _validate_rule_payload(
        session,
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
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(PersonalRule, rule_id)
    if rule is None:
        return False
    session.delete(rule)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return True


def list_rules(session: Session, *, active_only: bool = False) -> list[PersonalRule]:
    stmt = select(PersonalRule).order_by(PersonalRule.priority.asc(), PersonalRule.id.asc())
    if active_only:
        stmt = stmt.where(PersonalRule.active.is_(True))
    return list(session.execute(stmt).scalars().all())


def load_rule_matcher(session: Session) -> PersonalRuleMatcher:
    """Load active personal rules once for a batch operation."""

    return PersonalRuleMatcher(tuple(list_rules(session, active_only=True)))


def find_matching_rule(
    session: Session,
    *,
    merchant: str | None,
    title: str | None,
) -> PersonalRule | None:
    return load_rule_matcher(session).find(merchant=merchant, title=title)


def effect_for_transaction(
    session: Session,
    *,
    merchant: str | None,
    title: str | None,
) -> RuleEffect | None:
    return load_rule_matcher(session).effect(merchant=merchant, title=title)


def _effect_for_rule(rule: PersonalRule) -> RuleEffect:
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
        session.flush()
        return existing
    return _add_rule(
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
