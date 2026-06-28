from finance.transactions.merchants import merchant_canonical_key, merchant_key


def test_merchant_canonical_key_groups_brand_variants() -> None:
    keys = {
        merchant_canonical_key("BIEDRONKA 1234 WARSZAWA"),
        merchant_canonical_key("Biedronka Warszawa"),
        merchant_canonical_key("BIEDRONKA PAYU"),
        merchant_canonical_key("Biedronka"),
    }

    assert keys == {"biedronka"}


def test_merchant_canonical_key_groups_legal_suffixes() -> None:
    assert merchant_canonical_key("Lidl sp. z o.o.") == merchant_canonical_key(
        "LIDL 1234"
    )


def test_merchant_key_uses_title_fallback() -> None:
    assert merchant_key("", "LIDL zakupy karta") == "lidl zakupy karta"
    assert merchant_canonical_key("", "LIDL zakupy karta") == "lidl"


def test_merchant_key_prefers_title_for_generic_bank_label() -> None:
    assert merchant_key("CARD PAYMENT", "CARD PAYMENT NETFLIX.COM") == "card payment netflix com"
    assert merchant_canonical_key("CARD PAYMENT", "CARD PAYMENT NETFLIX.COM") == "netflix"


def test_person_like_merchants_are_not_reduced_to_first_name() -> None:
    assert merchant_canonical_key("Jan Kowalski") == "jan kowalski"
    assert merchant_canonical_key("Anna Nowak") == "anna nowak"
