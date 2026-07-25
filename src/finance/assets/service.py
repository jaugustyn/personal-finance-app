"""Approximate asset valuation, history and lifecycle operations."""

from __future__ import annotations

import calendar
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from finance.assets.types import (
    AssetAccountView,
    AssetBreakdownView,
    AssetFxRecomputeResult,
    AssetHistoryPointView,
    AssetHistoryView,
    AssetItemView,
    AssetOverviewView,
    AssetValueView,
)
from finance.currencies import BASE_CURRENCY, MissingFxRate, convert_amount, normalize_currency
from finance.currencies.providers import FxRateProvider
from finance.db import command_transaction
from finance.domain.models import AssetAccount, AssetItem, AssetValuation

ACCOUNT_KINDS = frozenset({"bank", "brokerage", "retirement", "crypto", "physical", "other"})
ACCOUNT_WRAPPERS = frozenset({"standard", "ike", "ikze", "ppk"})
TRACKING_MODES = frozenset({"aggregate", "detailed"})
ASSET_TYPES = frozenset(
    {
        "cash",
        "savings_account",
        "deposit",
        "bond",
        "stock",
        "etf",
        "fund",
        "crypto",
        "precious_metal",
        "loan_receivable",
        "other",
    }
)
REVIEW_INTERVALS = frozenset({7, 30, 90, 180})
INPUT_MODES = frozenset({"total", "unit_price"})
GROWTH_MODES = frozenset({"none", "fixed_rate"})
COMPOUNDING_MODES = frozenset({"simple", "daily", "monthly", "yearly"})
HISTORY_RANGES = frozenset({"3m", "1y", "all"})
MAX_HISTORY_POINTS = 120
FIXED_GROWTH_ASSET_TYPES = frozenset({"savings_account", "deposit", "loan_receivable"})

VALUE_QUANTUM = Decimal("0.00000001")
MONEY_QUANTUM = Decimal("0.01")
SHARE_QUANTUM = Decimal("0.0001")
MAX_TOTAL_VALUE = Decimal("999999999999.99999999")
MAX_QUANTITY = Decimal("9999999999999999.99999999")


class AssetValidationError(ValueError):
    """Raised when an asset command violates the domain contract."""


class AssetConflictError(ValueError):
    """Raised when an asset mutation conflicts with existing history."""


def _require_active_account(account: AssetAccount) -> None:
    if account.archived_at is not None:
        raise AssetConflictError("Restore the asset account before changing it.")


def _require_active_item(session: Session, item: AssetItem) -> None:
    if item.archived_at is not None:
        raise AssetConflictError("Restore the asset item before changing it.")
    account = session.get(AssetAccount, item.account_id)
    if account is None:  # pragma: no cover - protected by the foreign key
        raise AssetConflictError("Asset account not found.")
    _require_active_account(account)


def _quant_value(value: Decimal) -> Decimal:
    return Decimal(value).quantize(VALUE_QUANTUM, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _name(value: str, *, field: str = "Name") -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise AssetValidationError(f"{field} cannot be empty.")
    return normalized


def _optional_text(value: str | None) -> str | None:
    normalized = " ".join(value.split()) if value else ""
    return normalized or None


def _validate_account_values(*, kind: str, wrapper: str, tracking_mode: str) -> None:
    if kind not in ACCOUNT_KINDS:
        raise AssetValidationError("Unsupported asset account kind.")
    if wrapper not in ACCOUNT_WRAPPERS:
        raise AssetValidationError("Unsupported asset account wrapper.")
    if tracking_mode not in TRACKING_MODES:
        raise AssetValidationError("Unsupported asset account tracking mode.")
    if wrapper != "standard" and kind != "retirement":
        raise AssetValidationError("IKE, IKZE and PPK require a retirement account kind.")


def _validate_asset_type(value: str) -> str:
    if value not in ASSET_TYPES:
        raise AssetValidationError("Unsupported asset type.")
    return value


def _validate_growth_support(*, asset_type: str, growth_mode: str) -> None:
    if growth_mode == "fixed_rate" and asset_type not in FIXED_GROWTH_ASSET_TYPES:
        raise AssetValidationError("Fixed-rate growth is not supported for this asset type.")


def _require_growth_compatible_type(
    session: Session,
    *,
    item_id: int,
    asset_type: str,
) -> None:
    if asset_type in FIXED_GROWTH_ASSET_TYPES:
        return
    has_fixed_growth = bool(
        session.execute(
            select(func.count(AssetValuation.id)).where(
                AssetValuation.item_id == item_id,
                AssetValuation.growth_mode == "fixed_rate",
            )
        ).scalar_one()
    )
    if has_fixed_growth:
        raise AssetConflictError("Disable fixed-rate growth before changing the asset type.")


def _validate_review_interval(value: int | None) -> int | None:
    if value is not None and value not in REVIEW_INTERVALS:
        raise AssetValidationError("Unsupported valuation review interval.")
    return value


def _normalize_symbol(value: str | None) -> str | None:
    normalized = value.strip().upper() if value else ""
    return normalized or None


def _normalize_isin(value: str | None) -> str | None:
    normalized = value.strip().upper().replace(" ", "") if value else ""
    if normalized and (len(normalized) != 12 or not normalized.isalnum()):
        raise AssetValidationError("ISIN must contain 12 letters or digits.")
    return normalized or None


def _has_valuations(session: Session, account_id: int) -> bool:
    return (
        session.execute(
            select(func.count(AssetValuation.id))
            .join(AssetItem, AssetItem.id == AssetValuation.item_id)
            .where(AssetItem.account_id == account_id)
        ).scalar_one()
        > 0
    )


def _valuation_total(
    *,
    input_mode: str,
    total_value: Decimal | None,
    quantity: Decimal | None,
    unit_price: Decimal | None,
) -> tuple[Decimal, Decimal | None, Decimal | None]:
    if input_mode not in INPUT_MODES:
        raise AssetValidationError("Unsupported asset valuation input mode.")
    if input_mode == "total":
        if total_value is None:
            raise AssetValidationError("Total asset value must be non-negative.")
        total = Decimal(total_value)
        if not total.is_finite() or total < 0:
            raise AssetValidationError("Total asset value must be non-negative.")
        if total > MAX_TOTAL_VALUE:
            raise AssetValidationError("Total asset value is too large.")
        return _quant_value(total), None, None
    if quantity is None or unit_price is None:
        raise AssetValidationError("Quantity and unit price are required.")
    quantity = Decimal(quantity)
    unit_price = Decimal(unit_price)
    if not quantity.is_finite() or not unit_price.is_finite() or quantity < 0 or unit_price < 0:
        raise AssetValidationError("Quantity and unit price must be non-negative.")
    if quantity > MAX_QUANTITY:
        raise AssetValidationError("Quantity is too large.")
    if unit_price > MAX_TOTAL_VALUE:
        raise AssetValidationError("Unit price is too large.")
    total = quantity * unit_price
    if total > MAX_TOTAL_VALUE:
        raise AssetValidationError("Calculated asset value is too large.")
    return _quant_value(total), _quant_value(quantity), _quant_value(unit_price)


def _validate_valuation_date(value: date) -> date:
    if value > date.today():
        raise AssetValidationError("Valuation date cannot be in the future.")
    return value


def _growth_values(
    *,
    valuation_date: date,
    growth_mode: str,
    annual_rate_percent: Decimal | None,
    compounding: str | None,
    growth_end_date: date | None,
) -> tuple[Decimal | None, str | None, date | None]:
    if growth_mode not in GROWTH_MODES:
        raise AssetValidationError("Unsupported asset growth mode.")
    if growth_mode == "none":
        if (
            annual_rate_percent is not None
            or compounding is not None
            or growth_end_date is not None
        ):
            raise AssetValidationError("Growth settings require the fixed-rate mode.")
        return None, None, None
    if annual_rate_percent is None:
        raise AssetValidationError("Annual value change is required.")
    rate = Decimal(annual_rate_percent)
    if rate <= Decimal("-100") or rate > Decimal("1000"):
        raise AssetValidationError("Annual value change must be above -100% and at most 1000%.")
    if compounding not in COMPOUNDING_MODES:
        raise AssetValidationError("Unsupported compounding mode.")
    if growth_end_date is not None and growth_end_date < valuation_date:
        raise AssetValidationError("Growth end date cannot precede the valuation date.")
    return rate.quantize(Decimal("0.0001")), compounding, growth_end_date


def _conversion_fields(
    session: Session,
    *,
    total_value: Decimal,
    currency: str,
    valuation_date: date,
    allow_fetch: bool,
    provider: FxRateProvider | None,
) -> tuple[Decimal | None, Decimal | None, date | None, str | None]:
    try:
        converted = convert_amount(
            session,
            amount=total_value,
            currency=currency,
            rate_date=valuation_date,
            allow_fetch=allow_fetch,
            provider=provider,
        )
    except MissingFxRate:
        return None, None, None, None
    return (
        _money(converted.amount_base),
        Decimal(converted.fx_rate),
        converted.fx_rate_date,
        converted.fx_rate_source,
    )


def _add_valuation(
    session: Session,
    item: AssetItem,
    values: dict[str, Any],
    *,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> AssetValuation:
    valuation_date = _validate_valuation_date(cast(date, values["valuation_date"]))
    input_mode = str(values.get("input_mode", "total"))
    total, quantity, unit_price = _valuation_total(
        input_mode=input_mode,
        total_value=cast(Decimal | None, values.get("total_value")),
        quantity=cast(Decimal | None, values.get("quantity")),
        unit_price=cast(Decimal | None, values.get("unit_price")),
    )
    growth_mode = str(values.get("growth_mode", "none"))
    _validate_growth_support(
        asset_type=item.asset_type,
        growth_mode=growth_mode,
    )
    rate, compounding, growth_end_date = _growth_values(
        valuation_date=valuation_date,
        growth_mode=growth_mode,
        annual_rate_percent=cast(Decimal | None, values.get("annual_rate_percent")),
        compounding=cast(str | None, values.get("compounding")),
        growth_end_date=cast(date | None, values.get("growth_end_date")),
    )
    amount_pln, fx_rate, fx_rate_date, fx_rate_source = _conversion_fields(
        session,
        total_value=total,
        currency=item.currency,
        valuation_date=valuation_date,
        allow_fetch=allow_fetch,
        provider=provider,
    )
    row = AssetValuation(
        item_id=item.id,
        valuation_date=valuation_date,
        input_mode=input_mode,
        total_value=total,
        quantity=quantity,
        unit_price=unit_price,
        currency=item.currency,
        amount_pln=amount_pln,
        fx_rate=fx_rate,
        fx_rate_date=fx_rate_date,
        fx_rate_source=fx_rate_source,
        growth_mode=growth_mode,
        annual_rate_percent=rate,
        compounding=compounding,
        growth_end_date=growth_end_date,
        source="manual",
    )
    session.add(row)
    session.flush()
    return row


def create_account(
    session: Session,
    *,
    name: str,
    institution: str | None,
    kind: str,
    wrapper: str,
    tracking_mode: str,
    default_currency: str,
    notes: str | None,
    aggregate_asset_type: str | None = None,
    review_interval_days: int | None = 30,
    initial_valuation: dict[str, Any] | None = None,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> AssetAccount:
    _validate_account_values(kind=kind, wrapper=wrapper, tracking_mode=tracking_mode)
    currency = normalize_currency(default_currency)
    if tracking_mode == "aggregate":
        if aggregate_asset_type is None or initial_valuation is None:
            raise AssetValidationError(
                "Aggregate accounts require an asset type and initial valuation."
            )
        _validate_asset_type(aggregate_asset_type)
        _validate_review_interval(review_interval_days)
    elif aggregate_asset_type is not None or initial_valuation is not None:
        raise AssetValidationError("Initial account valuation is only available in aggregate mode.")
    row = AssetAccount(
        name=_name(name, field="Account name"),
        institution=_optional_text(institution),
        kind=kind,
        wrapper=wrapper,
        tracking_mode=tracking_mode,
        default_currency=currency,
        notes=_optional_text(notes),
    )
    try:
        with command_transaction(session):
            session.add(row)
            session.flush()
            if tracking_mode == "aggregate":
                item = AssetItem(
                    account_id=row.id,
                    name=row.name,
                    asset_type=cast(str, aggregate_asset_type),
                    currency=currency,
                    review_interval_days=review_interval_days,
                    is_aggregate_summary=True,
                )
                session.add(item)
                session.flush()
                _add_valuation(
                    session,
                    item,
                    cast(dict[str, Any], initial_valuation),
                    allow_fetch=allow_fetch,
                    provider=provider,
                )
    except IntegrityError as exc:
        raise AssetConflictError("An asset valuation already exists for this date.") from exc
    session.refresh(row)
    return row


def update_account(
    session: Session,
    account_id: int,
    values: dict[str, Any],
) -> AssetAccount | None:
    row = session.get(AssetAccount, account_id)
    if row is None:
        return None
    _require_active_account(row)
    if "tracking_mode" in values:
        raise AssetConflictError("Tracking mode cannot change after account creation.")
    has_history = _has_valuations(session, account_id)
    new_kind = str(values.get("kind", row.kind))
    new_wrapper = str(values.get("wrapper", row.wrapper))
    _validate_account_values(
        kind=new_kind,
        wrapper=new_wrapper,
        tracking_mode=row.tracking_mode,
    )
    with command_transaction(session):
        if "name" in values:
            row.name = _name(str(values["name"]), field="Account name")
        if "institution" in values:
            row.institution = _optional_text(cast(str | None, values["institution"]))
        row.kind = new_kind
        row.wrapper = new_wrapper
        if "default_currency" in values:
            currency = normalize_currency(str(values["default_currency"]))
            if (
                row.tracking_mode == "aggregate"
                and has_history
                and currency != row.default_currency
            ):
                raise AssetConflictError("Currency cannot change after the first valuation.")
            row.default_currency = currency
            if row.tracking_mode == "aggregate":
                summary = session.execute(
                    select(AssetItem).where(
                        AssetItem.account_id == row.id,
                        AssetItem.is_aggregate_summary.is_(True),
                    )
                ).scalar_one_or_none()
                if summary is not None:
                    summary.currency = currency
        if "notes" in values:
            row.notes = _optional_text(cast(str | None, values["notes"]))
        if row.tracking_mode == "aggregate":
            summary = session.execute(
                select(AssetItem).where(
                    AssetItem.account_id == row.id,
                    AssetItem.is_aggregate_summary.is_(True),
                )
            ).scalar_one_or_none()
            if summary is None:  # pragma: no cover - protected by domain invariants
                raise AssetConflictError("Aggregate account summary is missing.")
            if "aggregate_asset_type" in values:
                asset_type = values["aggregate_asset_type"]
                if asset_type is None:
                    raise AssetValidationError("Aggregate asset type is required.")
                validated_type = _validate_asset_type(str(asset_type))
                _require_growth_compatible_type(
                    session,
                    item_id=summary.id,
                    asset_type=validated_type,
                )
                summary.asset_type = validated_type
            if "review_interval_days" in values:
                summary.review_interval_days = _validate_review_interval(
                    cast(int | None, values["review_interval_days"])
                )
        elif values.get("aggregate_asset_type") is not None or ("review_interval_days" in values):
            raise AssetValidationError("Aggregate settings require aggregate tracking mode.")
    session.refresh(row)
    return row


def set_account_archived(session: Session, account_id: int, *, archived: bool) -> bool:
    row = session.get(AssetAccount, account_id)
    if row is None:
        return False
    with command_transaction(session):
        row.archived_at = datetime.now(UTC) if archived else None
    return True


def create_item(
    session: Session,
    account_id: int,
    *,
    name: str,
    asset_type: str,
    currency: str | None,
    symbol: str | None,
    isin: str | None,
    review_interval_days: int | None,
    notes: str | None,
    initial_valuation: dict[str, Any] | None = None,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> AssetItem | None:
    account = session.get(AssetAccount, account_id)
    if account is None:
        return None
    _require_active_account(account)
    if account.tracking_mode != "detailed":
        raise AssetConflictError("Items can only be added to detailed accounts.")
    row = AssetItem(
        account_id=account_id,
        name=_name(name, field="Asset name"),
        asset_type=_validate_asset_type(asset_type),
        currency=normalize_currency(currency or account.default_currency),
        symbol=_normalize_symbol(symbol),
        isin=_normalize_isin(isin),
        review_interval_days=_validate_review_interval(review_interval_days),
        notes=_optional_text(notes),
        is_aggregate_summary=False,
    )
    try:
        with command_transaction(session):
            session.add(row)
            session.flush()
            if initial_valuation is not None:
                _add_valuation(
                    session,
                    row,
                    initial_valuation,
                    allow_fetch=allow_fetch,
                    provider=provider,
                )
    except IntegrityError as exc:
        raise AssetConflictError("An asset valuation already exists for this date.") from exc
    session.refresh(row)
    return row


def update_item(session: Session, item_id: int, values: dict[str, Any]) -> AssetItem | None:
    row = session.get(AssetItem, item_id)
    if row is None:
        return None
    _require_active_item(session, row)
    if row.is_aggregate_summary:
        raise AssetConflictError("Aggregate account values are edited through the account.")
    has_history = bool(
        session.execute(
            select(func.count(AssetValuation.id)).where(AssetValuation.item_id == item_id)
        ).scalar_one()
    )
    with command_transaction(session):
        if "name" in values:
            row.name = _name(str(values["name"]), field="Asset name")
        if "asset_type" in values:
            validated_type = _validate_asset_type(str(values["asset_type"]))
            _require_growth_compatible_type(
                session,
                item_id=row.id,
                asset_type=validated_type,
            )
            row.asset_type = validated_type
        if "currency" in values:
            currency = normalize_currency(str(values["currency"]))
            if has_history and currency != row.currency:
                raise AssetConflictError("Currency cannot change after the first valuation.")
            row.currency = currency
        if "symbol" in values:
            row.symbol = _normalize_symbol(cast(str | None, values["symbol"]))
        if "isin" in values:
            row.isin = _normalize_isin(cast(str | None, values["isin"]))
        if "review_interval_days" in values:
            row.review_interval_days = _validate_review_interval(
                cast(int | None, values["review_interval_days"])
            )
        if "notes" in values:
            row.notes = _optional_text(cast(str | None, values["notes"]))
    session.refresh(row)
    return row


def set_item_archived(session: Session, item_id: int, *, archived: bool) -> bool:
    row = session.get(AssetItem, item_id)
    if row is None or row.is_aggregate_summary:
        return False
    with command_transaction(session):
        row.archived_at = datetime.now(UTC) if archived else None
    return True


def add_valuation(
    session: Session,
    item_id: int,
    values: dict[str, Any],
    *,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> AssetValuation | None:
    item = session.get(AssetItem, item_id)
    if item is None:
        return None
    _require_active_item(session, item)
    try:
        with command_transaction(session):
            row = _add_valuation(
                session,
                item,
                values,
                allow_fetch=allow_fetch,
                provider=provider,
            )
    except IntegrityError as exc:
        raise AssetConflictError("An asset valuation already exists for this date.") from exc
    session.refresh(row)
    return row


def update_valuation(
    session: Session,
    valuation_id: int,
    values: dict[str, Any],
    *,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> AssetValuation | None:
    row = session.get(AssetValuation, valuation_id)
    if row is None:
        return None
    item = session.get(AssetItem, row.item_id)
    if item is None:  # pragma: no cover - protected by the foreign key
        return None
    _require_active_item(session, item)
    merged = {
        "valuation_date": values.get("valuation_date", row.valuation_date),
        "input_mode": values.get("input_mode", row.input_mode),
        "total_value": values.get("total_value", row.total_value),
        "quantity": values.get("quantity", row.quantity),
        "unit_price": values.get("unit_price", row.unit_price),
        "growth_mode": values.get("growth_mode", row.growth_mode),
        "annual_rate_percent": values.get("annual_rate_percent", row.annual_rate_percent),
        "compounding": values.get("compounding", row.compounding),
        "growth_end_date": values.get("growth_end_date", row.growth_end_date),
    }
    if values.get("growth_mode") == "none":
        merged["annual_rate_percent"] = None
        merged["compounding"] = None
        merged["growth_end_date"] = None
    total, quantity, unit_price = _valuation_total(
        input_mode=str(merged["input_mode"]),
        total_value=cast(Decimal | None, merged["total_value"]),
        quantity=cast(Decimal | None, merged["quantity"]),
        unit_price=cast(Decimal | None, merged["unit_price"]),
    )
    valuation_date = _validate_valuation_date(cast(date, merged["valuation_date"]))
    _validate_growth_support(
        asset_type=item.asset_type,
        growth_mode=str(merged["growth_mode"]),
    )
    rate, compounding, growth_end_date = _growth_values(
        valuation_date=valuation_date,
        growth_mode=str(merged["growth_mode"]),
        annual_rate_percent=cast(Decimal | None, merged["annual_rate_percent"]),
        compounding=cast(str | None, merged["compounding"]),
        growth_end_date=cast(date | None, merged["growth_end_date"]),
    )
    amount_pln, fx_rate, fx_rate_date, fx_rate_source = _conversion_fields(
        session,
        total_value=total,
        currency=item.currency,
        valuation_date=valuation_date,
        allow_fetch=allow_fetch,
        provider=provider,
    )
    try:
        with command_transaction(session):
            row.valuation_date = valuation_date
            row.input_mode = str(merged["input_mode"])
            row.total_value = total
            row.quantity = quantity
            row.unit_price = unit_price
            row.currency = item.currency
            row.amount_pln = amount_pln
            row.fx_rate = fx_rate
            row.fx_rate_date = fx_rate_date
            row.fx_rate_source = fx_rate_source
            row.growth_mode = str(merged["growth_mode"])
            row.annual_rate_percent = rate
            row.compounding = compounding
            row.growth_end_date = growth_end_date
    except IntegrityError as exc:
        raise AssetConflictError("An asset valuation already exists for this date.") from exc
    session.refresh(row)
    return row


def delete_valuation(session: Session, valuation_id: int) -> bool:
    row = session.get(AssetValuation, valuation_id)
    if row is None:
        return False
    item = session.get(AssetItem, row.item_id)
    if item is None:  # pragma: no cover - protected by the foreign key
        return False
    _require_active_item(session, item)
    with command_transaction(session):
        session.delete(row)
    return True


def list_valuations(session: Session, item_id: int) -> list[AssetValuation] | None:
    if session.get(AssetItem, item_id) is None:
        return None
    return list(
        session.execute(
            select(AssetValuation)
            .where(AssetValuation.item_id == item_id)
            .order_by(AssetValuation.valuation_date.desc(), AssetValuation.id.desc())
        ).scalars()
    )


def _growth_factor(row: AssetValuation, as_of: date) -> Decimal:
    if row.growth_mode != "fixed_rate" or as_of <= row.valuation_date:
        return Decimal(1)
    target = min(as_of, row.growth_end_date) if row.growth_end_date else as_of
    days = max(0, (target - row.valuation_date).days)
    rate = Decimal(row.annual_rate_percent or 0) / Decimal(100)
    if row.compounding == "simple":
        return max(
            Decimal(0),
            Decimal(1) + rate * Decimal(days) / Decimal(365),
        )
    periods = {"daily": 365, "monthly": 12, "yearly": 1}[str(row.compounding)]
    with localcontext() as context:
        context.prec = 32
        return (Decimal(1) + rate / Decimal(periods)) ** (
            Decimal(periods) * Decimal(days) / Decimal(365)
        )


def _latest_valuation(rows: list[AssetValuation], as_of: date) -> AssetValuation | None:
    eligible = (row for row in rows if row.valuation_date <= as_of)
    return max(eligible, key=lambda row: (row.valuation_date, row.id), default=None)


def _empty_value(item: AssetItem, *, as_of: date) -> AssetValueView:
    return AssetValueView(
        as_of=as_of,
        valuation_id=None,
        valuation_date=None,
        native_value=None,
        currency=item.currency,
        amount_pln=None,
        growth_mode=None,
        projected=False,
        stale=False,
        matured=False,
        unconverted=False,
        fx_rate_date=None,
        fx_rate_source=None,
    )


def _value_from_valuation(
    item: AssetItem,
    row: AssetValuation | None,
    *,
    as_of: date,
) -> AssetValueView:
    if row is None:
        return _empty_value(item, as_of=as_of)
    factor = _growth_factor(row, as_of)
    native_value = _quant_value(Decimal(row.total_value) * factor)
    amount_pln = _money(Decimal(row.amount_pln) * factor) if row.amount_pln is not None else None
    matured = bool(row.growth_end_date and as_of >= row.growth_end_date)
    protected_by_maturity = bool(row.growth_end_date and as_of < row.growth_end_date)
    stale = bool(
        not matured
        and not protected_by_maturity
        and item.review_interval_days is not None
        and (as_of - row.valuation_date).days > item.review_interval_days
    )
    return AssetValueView(
        as_of=as_of,
        valuation_id=row.id,
        valuation_date=row.valuation_date,
        native_value=native_value,
        currency=row.currency,
        amount_pln=amount_pln,
        growth_mode=row.growth_mode,
        projected=row.growth_mode == "fixed_rate" and as_of > row.valuation_date,
        stale=stale,
        matured=matured,
        unconverted=row.currency != BASE_CURRENCY and amount_pln is None,
        fx_rate_date=row.fx_rate_date,
        fx_rate_source=row.fx_rate_source,
    )


def _value_at_sorted(
    item: AssetItem,
    rows: tuple[AssetValuation, ...],
    dates: tuple[date, ...],
    *,
    as_of: date,
) -> AssetValueView:
    index = bisect_right(dates, as_of) - 1
    row = rows[index] if index >= 0 else None
    return _value_from_valuation(item, row, as_of=as_of)


def value_at(item: AssetItem, rows: list[AssetValuation], *, as_of: date) -> AssetValueView:
    return _value_from_valuation(
        item,
        _latest_valuation(rows, as_of),
        as_of=as_of,
    )


def _load_accounts(session: Session, *, include_archived: bool) -> list[AssetAccount]:
    query = select(AssetAccount).options(
        selectinload(AssetAccount.items).selectinload(AssetItem.valuations)
    )
    if not include_archived:
        query = query.where(AssetAccount.archived_at.is_(None))
    return list(
        session.execute(query.order_by(AssetAccount.name, AssetAccount.id)).scalars().unique()
    )


def _load_account(
    session: Session,
    account_id: int,
    *,
    include_archived: bool,
) -> AssetAccount | None:
    query = (
        select(AssetAccount)
        .options(selectinload(AssetAccount.items).selectinload(AssetItem.valuations))
        .where(AssetAccount.id == account_id)
    )
    if not include_archived:
        query = query.where(AssetAccount.archived_at.is_(None))
    return session.execute(query).scalars().unique().one_or_none()


def _item_is_active(item: AssetItem, as_of: date) -> bool:
    return item.archived_at is None or item.archived_at.date() > as_of


def _account_is_active(account: AssetAccount, as_of: date) -> bool:
    return account.archived_at is None or account.archived_at.date() > as_of


def _item_view(item: AssetItem, *, as_of: date) -> AssetItemView:
    current = value_at(item, list(item.valuations), as_of=as_of)
    return AssetItemView(
        id=item.id,
        account_id=item.account_id,
        name=item.name,
        asset_type=item.asset_type,
        currency=item.currency,
        symbol=item.symbol,
        isin=item.isin,
        review_interval_days=item.review_interval_days,
        notes=item.notes,
        archived_at=item.archived_at,
        current_value=current,
    )


def _account_view(
    account: AssetAccount,
    *,
    target: date,
    include_archived: bool,
) -> AssetAccountView:
    account_target = (
        min(target, account.archived_at.date()) if account.archived_at is not None else target
    )
    item_views_by_id = {
        item.id: _item_view(
            item,
            as_of=(
                min(account_target, item.archived_at.date())
                if item.archived_at is not None
                else account_target
            ),
        )
        for item in account.items
    }
    active_items = [item for item in account.items if _item_is_active(item, account_target)]
    active_item_views = [item_views_by_id[item.id] for item in active_items]
    amount_pln = _money(
        sum(
            (
                item.current_value.amount_pln
                for item in active_item_views
                if item.current_value.amount_pln is not None
            ),
            Decimal(0),
        )
    )
    summary = next(
        (item for item in active_item_views if _summary_item(account, item.id)),
        None,
    )
    public_items = (
        []
        if account.tracking_mode == "aggregate"
        else [
            item_views_by_id[item.id]
            for item in account.items
            if not _summary_item(account, item.id)
            and (include_archived or _item_is_active(item, account_target))
        ]
    )
    return AssetAccountView(
        id=account.id,
        name=account.name,
        institution=account.institution,
        kind=account.kind,
        wrapper=account.wrapper,
        tracking_mode=account.tracking_mode,
        default_currency=account.default_currency,
        notes=account.notes,
        archived_at=account.archived_at,
        amount_pln=amount_pln,
        native_value=summary.current_value.native_value if summary else None,
        native_currency=summary.currency if summary else None,
        valuation_item_id=summary.id if summary else None,
        aggregate_asset_type=summary.asset_type if summary else None,
        review_interval_days=(summary.review_interval_days if summary else None),
        stale_count=sum(item.current_value.stale for item in active_item_views),
        matured_count=sum(item.current_value.matured for item in active_item_views),
        unconverted_count=sum(item.current_value.unconverted for item in active_item_views),
        missing_valuation_count=sum(
            item.current_value.valuation_id is None for item in active_item_views
        ),
        items=public_items,
    )


def list_accounts(
    session: Session,
    *,
    as_of: date | None = None,
    include_archived: bool = False,
) -> list[AssetAccountView]:
    target = as_of or date.today()
    return [
        _account_view(account, target=target, include_archived=include_archived)
        for account in _load_accounts(session, include_archived=include_archived)
    ]


def get_account_view(
    session: Session,
    account_id: int,
    *,
    as_of: date | None = None,
    include_archived: bool = True,
) -> AssetAccountView | None:
    account = _load_account(
        session,
        account_id,
        include_archived=include_archived,
    )
    return (
        _account_view(
            account,
            target=as_of or date.today(),
            include_archived=include_archived,
        )
        if account is not None
        else None
    )


def get_item_view(
    session: Session,
    item_id: int,
    *,
    as_of: date | None = None,
) -> AssetItemView | None:
    item = session.execute(
        select(AssetItem).options(selectinload(AssetItem.valuations)).where(AssetItem.id == item_id)
    ).scalar_one_or_none()
    return _item_view(item, as_of=as_of or date.today()) if item is not None else None


def _summary_item(account: AssetAccount, item_id: int) -> bool:
    return any(item.id == item_id and item.is_aggregate_summary for item in account.items)


def overview(session: Session, *, as_of: date | None = None) -> AssetOverviewView:
    target = as_of or date.today()
    accounts = _load_accounts(session, include_archived=False)
    breakdown: dict[str, Decimal] = defaultdict(Decimal)
    total = Decimal(0)
    item_count = stale = matured = unconverted = missing = 0
    for account in accounts:
        if not _account_is_active(account, target):
            continue
        for item in account.items:
            if not _item_is_active(item, target):
                continue
            item_count += 1
            current = value_at(item, list(item.valuations), as_of=target)
            stale += int(current.stale)
            matured += int(current.matured)
            unconverted += int(current.unconverted)
            missing += int(current.valuation_id is None)
            if current.amount_pln is not None:
                total += current.amount_pln
                breakdown[item.asset_type] += current.amount_pln
    total = _money(total)
    breakdown_rows = [
        AssetBreakdownView(
            asset_type=asset_type,
            amount_pln=_money(amount),
            share=(amount / total).quantize(SHARE_QUANTUM) if total else Decimal(0),
        )
        for asset_type, amount in sorted(breakdown.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    return AssetOverviewView(
        as_of=target,
        base_currency=BASE_CURRENCY,
        total_pln=total,
        account_count=len(accounts),
        item_count=item_count,
        stale_count=stale,
        matured_count=matured,
        unconverted_count=unconverted,
        missing_valuation_count=missing,
        breakdown=breakdown_rows,
    )


def _subtract_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _month_starts(start: date, end: date) -> list[date]:
    points = [start]
    cursor = _subtract_months(date(start.year, start.month, 1), -1)
    while cursor <= end:
        points.append(cursor)
        cursor = _subtract_months(cursor, -1)
    return points


def _weekly_samples(start: date, end: date) -> list[date]:
    points = [start]
    cursor = start + timedelta(days=7)
    while cursor < end:
        points.append(cursor)
        cursor += timedelta(days=7)
    points.append(end)
    return points


def _downsample_dates(points: list[date], *, limit: int) -> list[date]:
    if len(points) <= limit:
        return points
    last_index = len(points) - 1
    indexes = [round(index * last_index / (limit - 1)) for index in range(limit)]
    return [points[index] for index in indexes]


def history(
    session: Session,
    *,
    range_name: str,
    account_id: int | None = None,
    as_of: date | None = None,
) -> AssetHistoryView:
    if range_name not in HISTORY_RANGES:
        raise AssetValidationError("Unsupported asset history range.")
    target = as_of or date.today()
    if account_id is not None:
        account = _load_account(session, account_id, include_archived=True)
        if account is None:
            raise AssetValidationError("Asset account not found.")
        accounts = [account]
    else:
        accounts = _load_accounts(session, include_archived=True)
    valuation_dates = sorted(
        {
            valuation.valuation_date
            for account in accounts
            for item in account.items
            for valuation in item.valuations
            if valuation.valuation_date <= target
        }
    )
    if not valuation_dates:
        return AssetHistoryView(range=range_name, base_currency=BASE_CURRENCY, points=[])
    if range_name == "3m":
        start = _subtract_months(target, 3)
    elif range_name == "1y":
        start = target - timedelta(days=365)
    else:
        start = valuation_dates[0]
    if range_name == "3m":
        samples = [start + timedelta(days=offset) for offset in range((target - start).days + 1)]
    elif range_name == "1y":
        samples = _weekly_samples(start, target)
    else:
        samples = _month_starts(start, target)
        samples.extend(day for day in valuation_dates if day >= start)
        samples.append(target)
        samples = sorted(set(samples))
        samples = _downsample_dates(samples, limit=MAX_HISTORY_POINTS)

    timelines: dict[int, tuple[tuple[AssetValuation, ...], tuple[date, ...]]] = {}
    for account in accounts:
        for item in account.items:
            rows = tuple(
                sorted(
                    item.valuations,
                    key=lambda row: (row.valuation_date, row.id),
                )
            )
            timelines[item.id] = (rows, tuple(row.valuation_date for row in rows))
    points: list[AssetHistoryPointView] = []
    for sample in samples:
        total = Decimal(0)
        unconverted = 0
        for account in accounts:
            if not _account_is_active(account, sample):
                continue
            for item in account.items:
                if not _item_is_active(item, sample):
                    continue
                rows, dates = timelines[item.id]
                current = _value_at_sorted(item, rows, dates, as_of=sample)
                if current.amount_pln is not None:
                    total += current.amount_pln
                elif current.unconverted:
                    unconverted += 1
        points.append(
            AssetHistoryPointView(
                date=sample,
                amount_pln=_money(total),
                unconverted_count=unconverted,
            )
        )
    return AssetHistoryView(range=range_name, base_currency=BASE_CURRENCY, points=points)


def recompute_missing_fx(
    session: Session,
    *,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> AssetFxRecomputeResult:
    rows = list(
        session.execute(
            select(AssetValuation).where(
                AssetValuation.currency != BASE_CURRENCY,
                AssetValuation.amount_pln.is_(None),
            )
        ).scalars()
    )
    updated = missing = 0
    with command_transaction(session):
        for row in rows:
            amount_pln, fx_rate, fx_rate_date, fx_rate_source = _conversion_fields(
                session,
                total_value=Decimal(row.total_value),
                currency=row.currency,
                valuation_date=row.valuation_date,
                allow_fetch=allow_fetch,
                provider=provider,
            )
            if amount_pln is None:
                missing += 1
                continue
            row.amount_pln = amount_pln
            row.fx_rate = fx_rate
            row.fx_rate_date = fx_rate_date
            row.fx_rate_source = fx_rate_source
            updated += 1
    return AssetFxRecomputeResult(updated=updated, missing=missing)
