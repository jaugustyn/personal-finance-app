"use client";

import type { ReactNode } from "react";
import { DatePicker } from "@/components/date-range-picker";
import { HelpTooltip } from "@/components/help-tooltip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  AssetCompounding,
  AssetGrowthMode,
  AssetInputMode,
  AssetValuation,
  AssetValuationInput,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { COMPOUNDING_MODES, compoundingKey } from "../_lib/asset-options";
import {
  ASSET_VALUE_DECIMAL_PLACES,
  compactAssetDecimal,
} from "../_lib/asset-number-format";

export interface ValuationDraft {
  valuationDate: string;
  inputMode: AssetInputMode;
  totalValue: string;
  quantity: string;
  unitPrice: string;
  growthMode: AssetGrowthMode;
  annualRate: string;
  compounding: AssetCompounding;
  growthEndDate: string;
}

export function todayIso(): string {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${today.getFullYear()}-${month}-${day}`;
}

export function emptyValuationDraft(
  inputMode: AssetInputMode = "total",
): ValuationDraft {
  return {
    valuationDate: todayIso(),
    inputMode,
    totalValue: "",
    quantity: "",
    unitPrice: "",
    growthMode: "none",
    annualRate: "",
    compounding: "monthly",
    growthEndDate: "",
  };
}

export function valuationDraftIsEmpty(value: ValuationDraft): boolean {
  return (
    !value.totalValue.trim() &&
    !value.quantity.trim() &&
    !value.unitPrice.trim()
  );
}

export function valuationDraft(row: AssetValuation): ValuationDraft {
  return {
    valuationDate: row.valuation_date,
    inputMode: row.input_mode,
    totalValue: compactAssetDecimal(row.total_value),
    quantity: compactAssetDecimal(row.quantity),
    unitPrice: compactAssetDecimal(row.unit_price),
    growthMode: row.growth_mode,
    annualRate: compactAssetDecimal(row.annual_rate_percent),
    compounding: row.compounding ?? "monthly",
    growthEndDate: row.growth_end_date ?? "",
  };
}

function displayNumber(value: number): string {
  return compactAssetDecimal(value.toFixed(ASSET_VALUE_DECIMAL_PLACES)) || "0";
}

/** Start a new valuation from the latest known settings and today's value. */
export function valuationDraftForUpdate(
  row: AssetValuation,
  currentNativeValue?: number | string | null,
): ValuationDraft {
  const draft = valuationDraft(row);
  const valuationDate = todayIso();
  const currentValue =
    currentNativeValue == null
      ? Number(row.total_value)
      : Number(currentNativeValue);
  const quantity = Number(row.quantity);
  const growthExpired = Boolean(
    row.growth_end_date && row.growth_end_date < valuationDate,
  );

  return {
    ...draft,
    valuationDate,
    totalValue:
      row.input_mode === "total" && Number.isFinite(currentValue)
        ? displayNumber(currentValue)
        : draft.totalValue,
    unitPrice:
      row.input_mode === "unit_price" &&
      Number.isFinite(currentValue) &&
      Number.isFinite(quantity) &&
      quantity > 0
        ? displayNumber(currentValue / quantity)
        : draft.unitPrice,
    growthMode: growthExpired ? "none" : draft.growthMode,
    annualRate: growthExpired ? "" : draft.annualRate,
    growthEndDate: growthExpired ? "" : draft.growthEndDate,
  };
}

function normalizedNumber(value: string): string {
  return value.trim().replace(",", ".");
}

function isNonNegative(value: string): boolean {
  const number = Number(normalizedNumber(value));
  return value.trim() !== "" && Number.isFinite(number) && number >= 0;
}

export function isValuationValid(draft: ValuationDraft): boolean {
  if (!draft.valuationDate || draft.valuationDate > todayIso()) return false;
  if (draft.inputMode === "total" && !isNonNegative(draft.totalValue)) {
    return false;
  }
  if (
    draft.inputMode === "unit_price" &&
    (!isNonNegative(draft.quantity) || !isNonNegative(draft.unitPrice))
  ) {
    return false;
  }
  if (draft.growthMode === "fixed_rate") {
    const rate = Number(normalizedNumber(draft.annualRate));
    if (!Number.isFinite(rate) || rate <= -100 || rate > 1000) return false;
    if (draft.growthEndDate && draft.growthEndDate < draft.valuationDate) {
      return false;
    }
  }
  return true;
}

export function valuationPayload(draft: ValuationDraft): AssetValuationInput {
  return {
    valuation_date: draft.valuationDate,
    input_mode: draft.inputMode,
    total_value:
      draft.inputMode === "total" ? normalizedNumber(draft.totalValue) : null,
    quantity:
      draft.inputMode === "unit_price"
        ? normalizedNumber(draft.quantity)
        : null,
    unit_price:
      draft.inputMode === "unit_price"
        ? normalizedNumber(draft.unitPrice)
        : null,
    growth_mode: draft.growthMode,
    annual_rate_percent:
      draft.growthMode === "fixed_rate"
        ? normalizedNumber(draft.annualRate)
        : null,
    compounding: draft.growthMode === "fixed_rate" ? draft.compounding : null,
    growth_end_date:
      draft.growthMode === "fixed_rate" && draft.growthEndDate
        ? draft.growthEndDate
        : null,
  };
}

export function AssetValuationFields({
  value,
  onChange,
  currency,
  currencyControl,
  showGrowth = true,
  showInputMode = true,
}: {
  value: ValuationDraft;
  onChange: (value: ValuationDraft) => void;
  currency: string;
  currencyControl?: ReactNode;
  showGrowth?: boolean;
  showInputMode?: boolean;
}) {
  const { t } = useT();
  const update = <K extends keyof ValuationDraft>(
    key: K,
    next: ValuationDraft[K],
  ) => onChange({ ...value, [key]: next });

  return (
    <div className="space-y-6">
      {value.inputMode === "total" ? (
        <div className="flex flex-col gap-2">
          <Label htmlFor="asset-total-value">{t("assets.totalValue")}</Label>
          <div className="relative">
            <Input
              id="asset-total-value"
              inputMode="decimal"
              value={value.totalValue}
              onChange={(event) => update("totalValue", event.target.value)}
              className="pr-16"
              placeholder="0,00"
            />
            <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">
              {currency}
            </span>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="asset-quantity">{t("assets.quantity")}</Label>
            <Input
              id="asset-quantity"
              inputMode="decimal"
              value={value.quantity}
              onChange={(event) => update("quantity", event.target.value)}
              placeholder="0"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="asset-unit-price">{t("assets.unitPrice")}</Label>
            <div className="relative">
              <Input
                id="asset-unit-price"
                inputMode="decimal"
                value={value.unitPrice}
                onChange={(event) => update("unitPrice", event.target.value)}
                className="pr-16"
                placeholder="0,00"
              />
              <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">
                {currency}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="asset-valuation-date">
            {t("assets.valuationDate")}
          </Label>
          <DatePicker
            id="asset-valuation-date"
            value={value.valuationDate}
            onChange={(next) => update("valuationDate", next)}
            ariaLabel={t("assets.valuationDate")}
            max={todayIso()}
          />
        </div>
        {showInputMode || value.inputMode === "unit_price" ? (
          <div
            className={cn(
              "flex flex-col gap-2",
              currencyControl && "sm:col-span-2 sm:order-last",
            )}
          >
            <HelpTooltip content={t("assets.inputModeHint")}>
              <Label className={cn(currencyControl && "whitespace-nowrap")}>
                {t("assets.inputMode")}
              </Label>
            </HelpTooltip>
            <Select
              value={value.inputMode}
              onValueChange={(next: AssetInputMode) =>
                update("inputMode", next)
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="total" indicatorPosition="right">
                  {t("assets.inputMode.total")}
                </SelectItem>
                <SelectItem value="unit_price" indicatorPosition="right">
                  {t("assets.inputMode.unitPrice")}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}
        {currencyControl}
      </div>

      {showGrowth ? (
        <details className="border-t pt-5">
          <summary className="cursor-pointer text-sm font-medium">
            {t("assets.moreSettings")}
            {value.growthMode !== "none"
              ? ` – ${t("assets.growth.fixedRate")}`
              : ""}
          </summary>
          <div className="pt-4">
            <AssetGrowthFields value={value} onChange={onChange} />
          </div>
        </details>
      ) : null}
    </div>
  );
}

export function AssetGrowthFields({
  value,
  onChange,
}: {
  value: ValuationDraft;
  onChange: (value: ValuationDraft) => void;
}) {
  const { t } = useT();
  const update = <K extends keyof ValuationDraft>(
    key: K,
    next: ValuationDraft[K],
  ) => onChange({ ...value, [key]: next });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <HelpTooltip content={t("assets.annualRateHint")}>
          <Label>{t("assets.valueChange")}</Label>
        </HelpTooltip>
        <Select
          value={value.growthMode}
          onValueChange={(next: AssetGrowthMode) => update("growthMode", next)}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none" indicatorPosition="right">
              {t("assets.growth.none")}
            </SelectItem>
            <SelectItem value="fixed_rate" indicatorPosition="right">
              {t("assets.growth.fixedRate")}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {value.growthMode === "fixed_rate" ? (
        <div className="@container">
          <div className="grid gap-4 @min-[20rem]:grid-cols-2 @min-[34rem]:grid-cols-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="asset-annual-rate">
                {t("assets.annualRate")}
              </Label>
              <div className="relative">
                <Input
                  id="asset-annual-rate"
                  inputMode="decimal"
                  value={value.annualRate}
                  onChange={(event) => update("annualRate", event.target.value)}
                  className="pr-9"
                  placeholder="5,00"
                />
                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">
                  %
                </span>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <HelpTooltip content={t("assets.compoundingHint")}>
                <Label>{t("assets.compounding")}</Label>
              </HelpTooltip>
              <Select
                value={value.compounding}
                onValueChange={(next: AssetCompounding) =>
                  update("compounding", next)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COMPOUNDING_MODES.map((mode) => (
                    <SelectItem
                      key={mode}
                      value={mode}
                      indicatorPosition="right"
                    >
                      {t(compoundingKey(mode))}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2 @min-[20rem]:col-span-2 @min-[34rem]:col-span-1">
              <div className="flex items-center justify-between gap-3">
                <Label>{t("assets.growthEndDate")}</Label>
                {value.growthEndDate ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-auto p-0 text-xs text-muted-foreground hover:bg-transparent hover:text-foreground"
                    onClick={() => update("growthEndDate", "")}
                  >
                    {t("common.clear")}
                  </Button>
                ) : null}
              </div>
              <DatePicker
                value={value.growthEndDate}
                onChange={(next) => update("growthEndDate", next)}
                ariaLabel={t("assets.noEndDate")}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
