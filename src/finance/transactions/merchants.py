"""Merchant normalization, canonicalization and alias helpers."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.currencies import amount_base_expr
from finance.domain.models import MerchantAlias, Transaction
from finance.transactions.normalization import normalize_merchant
from finance.transactions.types import (
    MerchantAliasSuggestion,
    MerchantCandidate,
    MerchantCandidateVariant,
    MerchantIdentity,
)

MERCHANT_GROUP_STOPWORDS = {
    "blik",
    "card",
    "com",
    "internet",
    "online",
    "pay",
    "payment",
    "payu",
    "platnosc",
    "pos",
    "ref",
    "terminal",
    "transakcja",
    "visa",
    "zakup",
}
LEGAL_SUFFIXES = {"sa", "s", "a", "sp", "z", "oo", "o", "pl", "ltd", "llc"}
LOCATION_TOKENS = {
    "amsterdam",
    "bialystok",
    "bydgoszcz",
    "gdansk",
    "gdynia",
    "katowice",
    "krakow",
    "lodz",
    "lublin",
    "poznan",
    "rzeszow",
    "szczecin",
    "torun",
    "warszawa",
    "wroclaw",
}
CANONICAL_STOPWORDS = MERCHANT_GROUP_STOPWORDS | LEGAL_SUFFIXES | LOCATION_TOKENS
GENERIC_MERCHANT_KEYS = {
    "blik",
    "card",
    "card payment",
    "payment",
    "pos",
    "visa",
    "visa payment",
    "zakup",
    "platnosc",
    "platnosc karta",
    "transakcja",
}


@dataclass
class _AliasSuggestionAccumulator:
    labels: Counter[str] = field(default_factory=Counter)
    count: int = 0
    total: Decimal = Decimal(0)
    canonical: str = ""


@dataclass
class _MerchantVariantAccumulator:
    labels: Counter[str] = field(default_factory=Counter)
    count: int = 0
    total: Decimal = Decimal(0)


@dataclass
class _MerchantCandidateAccumulator:
    labels: Counter[str] = field(default_factory=Counter)
    aliases: set[str] = field(default_factory=set)
    unresolved_aliases: set[str] = field(default_factory=set)
    variants: defaultdict[str, _MerchantVariantAccumulator] = field(
        default_factory=lambda: defaultdict(_MerchantVariantAccumulator)
    )
    count: int = 0
    total: Decimal = Decimal(0)


def compact_merchant_label(value: str | None) -> str:
    """Trim display text and collapse whitespace without changing punctuation."""
    return " ".join((value or "").split())


def merchant_display_label(merchant: str | None, title: str | None = None) -> str:
    """Return the best raw label for UI display."""
    merchant_label = compact_merchant_label(merchant)
    title_label = compact_merchant_label(title)
    if (
        merchant_label
        and title_label
        and _is_generic_merchant_key(normalize_merchant(merchant_label))
        and not _is_generic_merchant_key(normalize_merchant(title_label))
    ):
        return title_label
    return merchant_label or title_label


def merchant_key(merchant: str | None, title: str | None = None) -> str:
    """Stable normalized key for the raw merchant/title label."""
    return normalize_merchant(merchant_display_label(merchant, title))


def merchant_canonical_key(
    merchant: str | None,
    title: str | None = None,
    *,
    alias_map: dict[str, str] | None = None,
) -> str:
    """Canonical merchant key, using user aliases before heuristic fallback."""
    alias_key = merchant_key(merchant, title)
    if not alias_key:
        return ""
    if alias_map and alias_key in alias_map:
        return alias_map[alias_key]
    return heuristic_merchant_canonical_key(alias_key)


def heuristic_merchant_canonical_key(alias_key: str) -> str:
    tokens = [
        token
        for token in alias_key.split()
        if len(token) > 1
        and not token.isdigit()
        and not _looks_like_terminal_token(token)
        and token not in CANONICAL_STOPWORDS
    ]
    if not tokens:
        return alias_key
    if len(tokens) == 2 and _looks_like_person_name(tokens):
        return " ".join(tokens)
    return tokens[0]


def merchant_identity(
    merchant: str | None,
    title: str | None = None,
    *,
    alias_map: dict[str, str] | None = None,
    label_map: dict[str, str] | None = None,
) -> MerchantIdentity:
    alias_key = merchant_key(merchant, title)
    canonical_key = merchant_canonical_key(merchant, title, alias_map=alias_map)
    display_label = (
        label_map.get(canonical_key)
        if label_map and canonical_key in label_map
        else merchant_display_label(merchant, title)
    )
    return MerchantIdentity(
        alias_key=alias_key,
        canonical_key=canonical_key,
        display_label=display_label or canonical_key,
    )


def load_merchant_alias_maps(session: Session) -> tuple[dict[str, str], dict[str, str]]:
    rows = session.execute(select(MerchantAlias)).scalars().all()
    alias_map = {row.alias_key: row.canonical_key for row in rows}
    label_map = {
        row.canonical_key: compact_merchant_label(row.canonical_label)
        for row in rows
    }
    return alias_map, label_map


def list_aliases(session: Session) -> list[MerchantAlias]:
    rows = session.execute(select(MerchantAlias).order_by(MerchantAlias.alias_label))
    return list(rows.scalars())


def alias_usage_counts(
    session: Session,
    alias_keys: Iterable[str],
) -> dict[str, int]:
    keys = {key for key in alias_keys if key}
    counts = dict.fromkeys(keys, 0)
    if not keys:
        return counts

    rows = session.execute(select(Transaction.merchant, Transaction.title))
    for merchant, title in rows:
        alias_key = merchant_key(merchant, title)
        if alias_key in counts:
            counts[alias_key] += 1
    return counts


def create_aliases(
    session: Session,
    *,
    canonical_label: str,
    aliases: Iterable[str],
    canonical_key: str | None = None,
) -> list[MerchantAlias]:
    canonical_label = compact_merchant_label(canonical_label)
    canonical_key = (
        normalize_merchant(canonical_key)
        if canonical_key
        else heuristic_merchant_canonical_key(normalize_merchant(canonical_label))
    )
    if not canonical_label or not canonical_key:
        raise ValueError("canonical_label is required")

    existing = {
        row.alias_key: row for row in session.execute(select(MerchantAlias)).scalars()
    }
    existing_group_label = next(
        (
            row.canonical_label
            for row in existing.values()
            if row.canonical_key == canonical_key
        ),
        None,
    )
    if existing_group_label:
        canonical_label = existing_group_label
    out: list[MerchantAlias] = []
    for alias_label in aliases:
        label = compact_merchant_label(alias_label)
        alias_key = merchant_key(label)
        if not label or not alias_key:
            continue
        row = existing.get(alias_key)
        if row is None:
            row = MerchantAlias(
                alias_key=alias_key,
                alias_label=label,
                canonical_key=canonical_key,
                canonical_label=canonical_label,
            )
            session.add(row)
            existing[alias_key] = row
        else:
            row.alias_label = label
            row.canonical_key = canonical_key
            row.canonical_label = canonical_label
        out.append(row)
    if not out:
        raise ValueError("at least one alias is required")
    session.commit()
    for row in out:
        session.refresh(row)
    return out


def update_alias_group_label(
    session: Session,
    *,
    canonical_key: str,
    canonical_label: str,
) -> list[MerchantAlias]:
    canonical_key = normalize_merchant(canonical_key)
    canonical_label = compact_merchant_label(canonical_label)
    if not canonical_key or not canonical_label:
        raise ValueError("canonical_key and canonical_label are required")

    rows = list(
        session.execute(
            select(MerchantAlias).where(MerchantAlias.canonical_key == canonical_key)
        ).scalars()
    )
    for row in rows:
        row.canonical_label = canonical_label
    if rows:
        session.commit()
        for row in rows:
            session.refresh(row)
    return rows


def delete_alias(session: Session, alias_id: int) -> bool:
    row = session.get(MerchantAlias, alias_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


def alias_suggestions(
    session: Session,
    *,
    q: str,
    limit: int = 10,
) -> list[MerchantAliasSuggestion]:
    query = normalize_merchant(q)
    if not query:
        return []
    alias_map, label_map = load_merchant_alias_maps(session)
    rows = session.execute(
        select(Transaction.merchant, Transaction.title, amount_base_expr())
    ).all()
    variants: defaultdict[str, _AliasSuggestionAccumulator] = defaultdict(
        _AliasSuggestionAccumulator
    )
    for merchant, title, amount in rows:
        alias_key = merchant_key(merchant, title)
        if not alias_key or alias_key in alias_map:
            continue
        label = merchant_display_label(merchant, title)
        if query not in alias_key and query not in normalize_merchant(label):
            continue
        canonical_key = merchant_canonical_key(merchant, title, alias_map=alias_map)
        variant = variants[alias_key]
        variant.labels[label] += 1
        variant.count += 1
        variant.total += abs(Decimal(amount or 0))
        variant.canonical = canonical_key

    out: list[MerchantAliasSuggestion] = []
    for alias_key, variant in variants.items():
        canonical_key = variant.canonical
        out.append(
            MerchantAliasSuggestion(
                alias_key=alias_key,
                alias_label=(
                    variant.labels.most_common(1)[0][0]
                    if variant.labels
                    else alias_key
                ),
                canonical_key=canonical_key,
                canonical_label=label_map.get(canonical_key, canonical_key),
                count=variant.count,
                total_amount=variant.total,
            )
        )
    out.sort(key=lambda item: (item.count, item.total_amount), reverse=True)
    return out[:limit]


def alias_candidates(
    session: Session,
    *,
    min_variants: int = 2,
    limit: int = 20,
    q: str | None = None,
    sort_by: str = "count",
    sort_dir: str = "desc",
) -> list[MerchantCandidate]:
    alias_map, label_map = load_merchant_alias_maps(session)
    rows = session.execute(
        select(Transaction.merchant, Transaction.title, amount_base_expr()).where(
            *expense_category_candidate_filters(),
            Transaction.direction == "debit",
        )
    ).all()

    groups: defaultdict[str, _MerchantCandidateAccumulator] = defaultdict(
        _MerchantCandidateAccumulator
    )
    for merchant, title, amount in rows:
        identity = merchant_identity(
            merchant,
            title,
            alias_map=alias_map,
            label_map=label_map,
        )
        if not identity.canonical_key:
            continue
        label = merchant_display_label(merchant, title)
        alias_key = merchant_key(merchant, title)
        group = groups[identity.canonical_key]
        group.labels[label] += 1
        group.aliases.add(alias_key)
        if alias_map.get(alias_key) != identity.canonical_key:
            group.unresolved_aliases.add(alias_key)
        group.count += 1
        group.total += abs(Decimal(amount or 0))
        variant = group.variants[alias_key]
        variant.labels[label] += 1
        variant.count += 1
        variant.total += abs(Decimal(amount or 0))

    candidates: list[MerchantCandidate] = []
    for canonical_key, group in groups.items():
        unresolved_aliases = {
            alias for alias in group.unresolved_aliases if alias
        }
        if not unresolved_aliases:
            continue
        is_existing_group = canonical_key in label_map
        if not is_existing_group and len(unresolved_aliases) < min_variants:
            continue
        aliases = sorted(str(alias) for alias in unresolved_aliases)
        variant_rows: list[MerchantCandidateVariant] = []
        for alias_key, variant in group.variants.items():
            if alias_key not in unresolved_aliases:
                continue
            alias_label = (
                variant.labels.most_common(1)[0][0]
                if variant.labels
                else alias_key
            )
            variant_rows.append(
                MerchantCandidateVariant(
                    alias_key=alias_key,
                    alias_label=alias_label,
                    count=variant.count,
                    total_debit=variant.total,
                )
            )
        variant_rows.sort(key=lambda item: (item.count, item.total_debit), reverse=True)
        suggested_label = (
            variant_rows[0].alias_label
            if variant_rows
            else canonical_key
        )
        canonical_label = label_map.get(canonical_key) or suggested_label
        unresolved_count = sum(variant.count for variant in variant_rows)
        unresolved_total = sum(
            (variant.total_debit for variant in variant_rows),
            Decimal(0),
        )
        candidates.append(
            MerchantCandidate(
                canonical_key=canonical_key,
                canonical_label=canonical_label,
                suggested_label=suggested_label,
                aliases=aliases,
                variants=variant_rows,
                count=unresolved_count,
                total_debit=unresolved_total,
            )
        )
    query = normalize_merchant(q or "")
    if query:
        candidates = [
            candidate
            for candidate in candidates
            if query
            in normalize_merchant(
                " ".join(
                    [
                        candidate.canonical_key,
                        candidate.canonical_label,
                        candidate.suggested_label,
                        *candidate.aliases,
                        *(variant.alias_label for variant in candidate.variants),
                    ]
                )
            )
        ]

    sort_values: dict[
        str,
        Callable[[MerchantCandidate], str | int | Decimal],
    ] = {
        "suggested_label": lambda item: normalize_merchant(item.suggested_label),
        "variants": lambda item: len(item.variants),
        "count": lambda item: item.count,
        "total_debit": lambda item: item.total_debit,
    }
    if sort_by not in sort_values:
        raise ValueError(f"Unsupported merchant candidate sort: {sort_by}")
    if sort_dir not in {"asc", "desc"}:
        raise ValueError(f"Unsupported merchant candidate sort direction: {sort_dir}")

    candidates.sort(key=lambda item: item.canonical_key)
    candidates.sort(key=sort_values[sort_by], reverse=sort_dir == "desc")
    return candidates[:limit]


def _looks_like_terminal_token(token: str) -> bool:
    return any(ch.isdigit() for ch in token) and len(token) >= 4


def _looks_like_person_name(tokens: list[str]) -> bool:
    if len(tokens) != 2:
        return False
    if tokens[0] == tokens[1]:
        return False
    return all(2 <= len(token) <= 14 for token in tokens)


def _is_generic_merchant_key(key: str) -> bool:
    tokens = key.split()
    if not tokens:
        return True
    return key in GENERIC_MERCHANT_KEYS or all(
        token in MERCHANT_GROUP_STOPWORDS for token in tokens
    )
