from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from finance.domain.enums import BankSource, TransactionDirection, TransactionType
from finance.domain.models import MerchantAlias, Transaction
from finance.transactions.merchants import (
    alias_candidates,
    merchant_candidate_key,
    merchant_canonical_key,
    merchant_display_label,
    merchant_key,
)


def test_merchant_candidate_key_groups_brand_variants() -> None:
    keys = {
        merchant_candidate_key("BIEDRONKA 1234 WARSZAWA"),
        merchant_candidate_key("Biedronka Warszawa"),
        merchant_candidate_key("BIEDRONKA PAYU"),
        merchant_candidate_key("Biedronka"),
    }

    assert keys == {"biedronka"}


def test_merchant_candidate_key_groups_legal_suffixes() -> None:
    assert merchant_candidate_key("Lidl sp. z o.o.") == merchant_candidate_key(
        "LIDL 1234"
    )


def test_merchant_key_uses_title_fallback() -> None:
    assert merchant_key("", "LIDL zakupy karta") == "lidl zakupy karta"
    assert merchant_candidate_key("", "LIDL zakupy karta") == "lidl"


def test_merchant_display_label_collapses_whitespace() -> None:
    assert (
        merchant_display_label("  ZABKA Z1139 K.1    TRZEBINIA  ")
        == "ZABKA Z1139 K.1 TRZEBINIA"
    )


def test_merchant_key_prefers_title_for_generic_bank_label() -> None:
    assert merchant_key("CARD PAYMENT", "CARD PAYMENT NETFLIX.COM") == "card payment netflix com"
    assert merchant_candidate_key("CARD PAYMENT", "CARD PAYMENT NETFLIX.COM") == "netflix"


def test_person_like_merchants_are_not_reduced_to_first_name() -> None:
    assert merchant_candidate_key("Jan Kowalski") == "jan kowalski"
    assert merchant_candidate_key("Anna Nowak") == "anna nowak"


def test_unconfirmed_merchant_variants_remain_separate() -> None:
    assert merchant_canonical_key("ABC Market Centrum") == "abc market centrum"
    assert merchant_canonical_key("ABC Serwis Rowerowy") == "abc serwis rowerowy"


def test_saved_alias_is_the_trusted_merchant_identity() -> None:
    alias_map = {"abc market centrum": "abc"}

    assert (
        merchant_canonical_key("ABC Market Centrum", alias_map=alias_map) == "abc"
    )


def test_alias_candidates_for_existing_group_include_only_unresolved_aliases(
    db_session: Session,
) -> None:
    canonical_key = merchant_candidate_key("APTEKA PROMIENNA")
    saved_aliases = [
        merchant_key("APTEKA PROMIENNA"),
        merchant_key("APTEKA PROMIENNA 1111"),
    ]
    unresolved_aliases = [
        merchant_key("APTEKA PROMIENNA 1234"),
        merchant_key("APTEKA PROMIENNA 5678"),
    ]
    for alias_key in saved_aliases:
        db_session.add(
            MerchantAlias(
                alias_key=alias_key,
                alias_label=alias_key.upper(),
                canonical_key=canonical_key,
                canonical_label="APTEKA PROMIENNA",
            )
        )

    merchants = [
        ("APTEKA PROMIENNA", Decimal("-10.00")),
        ("APTEKA PROMIENNA 1111", Decimal("-20.00")),
        ("APTEKA PROMIENNA 1234", Decimal("-30.00")),
        ("APTEKA PROMIENNA 5678", Decimal("-40.00")),
    ]
    for index, (merchant, amount) in enumerate(merchants, start=1):
        db_session.add(
            Transaction(
                booking_date=date(2026, 1, index),
                amount=amount,
                currency="PLN",
                amount_base=amount,
                direction=TransactionDirection.DEBIT.value,
                merchant=merchant,
                title="",
                transaction_type=TransactionType.EXPENSE.value,
                source=BankSource.UNKNOWN.value,
                dedup_hash=f"alias-candidate-{index}",
                is_transfer=False,
            )
        )
    db_session.commit()

    candidates = alias_candidates(db_session, min_variants=2, limit=20)

    candidate = next(item for item in candidates if item.canonical_key == canonical_key)
    assert candidate.canonical_label == "APTEKA PROMIENNA"
    assert candidate.suggested_label in {"APTEKA PROMIENNA 1234", "APTEKA PROMIENNA 5678"}
    assert candidate.aliases == sorted(unresolved_aliases)
    assert {variant.alias_key for variant in candidate.variants} == set(unresolved_aliases)
    assert candidate.count == 2
    assert candidate.total_debit == Decimal("70.00")
