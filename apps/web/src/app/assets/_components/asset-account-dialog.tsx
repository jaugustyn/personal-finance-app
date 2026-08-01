"use client";

import { FormEvent, useState } from "react";
import {
  Check,
  ChevronDown,
  Layers3,
  Loader2,
  WalletCards,
} from "lucide-react";
import { CurrencyCombobox } from "@/components/currency-combobox";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  AssetAccount,
  AssetAccountInput,
  AssetAccountKind,
  AssetAccountWrapper,
  AssetTrackingMode,
  AssetType,
} from "@/lib/api";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  ASSET_TYPES,
  REVIEW_INTERVAL_OPTIONS,
  assetTypeCapabilities,
  assetTypeKey,
} from "../_lib/asset-options";
import {
  AssetGrowthFields,
  AssetValuationFields,
  emptyValuationDraft,
  isValuationValid,
  valuationPayload,
  valuationDraftIsEmpty,
  type ValuationDraft,
} from "./asset-valuation-fields";

type AccountProfile =
  | AssetAccountKind
  | Exclude<AssetAccountWrapper, "standard">;

const ACCOUNT_PROFILES = [
  { value: "bank", key: "assets.profile.bank" },
  { value: "brokerage", key: "assets.profile.brokerage" },
  { value: "retirement", key: "assets.profile.retirement" },
  { value: "ike", key: "assets.profile.ike" },
  { value: "ikze", key: "assets.profile.ikze" },
  { value: "ppk", key: "assets.profile.ppk" },
  { value: "crypto", key: "assets.profile.crypto" },
  { value: "physical", key: "assets.profile.physical" },
  { value: "other", key: "assets.profile.other" },
] as const satisfies readonly { value: AccountProfile; key: TranslationKey }[];

const AGGREGATE_ACCOUNT_PROFILES = ACCOUNT_PROFILES.filter(
  (profile) => profile.value !== "physical",
);

interface AccountDraft {
  name: string;
  institution: string;
  kind: AssetAccountKind;
  wrapper: AssetAccountWrapper;
  trackingMode: AssetTrackingMode;
  currency: string;
  assetType: AssetType;
  reviewInterval: string;
  notes: string;
  valuation: ValuationDraft;
}

function initialDraft(account?: AssetAccount | null): AccountDraft {
  const assetType = account?.aggregate_asset_type ?? "savings_account";
  return {
    name: account?.name ?? "",
    institution: account?.institution ?? "",
    kind: account?.kind ?? "bank",
    wrapper: account?.wrapper ?? "standard",
    trackingMode: account?.tracking_mode ?? "aggregate",
    currency: account?.default_currency ?? "PLN",
    assetType,
    reviewInterval: account
      ? account.review_interval_days == null
        ? "never"
        : String(account.review_interval_days)
      : "30",
    notes: account?.notes ?? "",
    valuation: emptyValuationDraft(
      assetTypeCapabilities(assetType).defaultInputMode,
    ),
  };
}

function accountProfile(
  kind: AssetAccountKind,
  wrapper: AssetAccountWrapper,
): AccountProfile {
  return wrapper === "standard" ? kind : wrapper;
}

function accountProfileValues(profile: AccountProfile): {
  kind: AssetAccountKind;
  wrapper: AssetAccountWrapper;
} {
  if (profile === "ike" || profile === "ikze" || profile === "ppk") {
    return { kind: "retirement", wrapper: profile };
  }
  return { kind: profile, wrapper: "standard" };
}

function defaultProfileForAsset(type: AssetType): AccountProfile {
  return assetTypeCapabilities(type).defaultAccountKind;
}

function TrackingModeCard({
  checked,
  icon: Icon,
  title,
  description,
  onClick,
}: {
  checked: boolean;
  icon: typeof WalletCards;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      onClick={onClick}
      className={cn(
        "relative flex min-h-[4.5rem] items-start gap-3 rounded-lg border p-3 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        checked
          ? "border-primary bg-primary/5"
          : "border-border bg-background hover:bg-muted/40",
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
          checked
            ? "bg-primary/10 text-primary"
            : "bg-muted text-muted-foreground",
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 pr-5">
        <span className="block text-sm font-medium text-foreground">{title}</span>
        <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
          {description}
        </span>
      </span>
      {checked ? (
        <Check className="absolute right-3 top-3 h-4 w-4 text-primary" />
      ) : null}
    </button>
  );
}

export function AssetAccountDialog({
  account,
  open,
  onOpenChange,
  onSubmit,
  pending,
}: {
  account?: AssetAccount | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: AssetAccountInput) => Promise<void>;
  pending: boolean;
}) {
  const { t } = useT();
  const editing = Boolean(account);
  const [draft, setDraft] = useState<AccountDraft>(() => initialDraft(account));
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const aggregate = draft.trackingMode === "aggregate";
  const capabilities = assetTypeCapabilities(draft.assetType);
  const showsAccountProfile =
    aggregate && capabilities.supportsAccountProfile;
  const canSave =
    draft.name.trim().length > 0 &&
    (editing || !aggregate || isValuationValid(draft.valuation));

  const update = <K extends keyof AccountDraft>(
    key: K,
    value: AccountDraft[K],
  ) => setDraft((current) => ({ ...current, [key]: value }));

  const updateProfile = (profile: AccountProfile) => {
    setDraft((current) => ({
      ...current,
      ...accountProfileValues(profile),
    }));
  };

  const updateAssetType = (assetType: AssetType) => {
    setDraft((current) => {
      const currentProfile = accountProfile(current.kind, current.wrapper);
      const followsDefault =
        currentProfile === defaultProfileForAsset(current.assetType);
      const currentCapabilities = assetTypeCapabilities(current.assetType);
      const nextCapabilities = assetTypeCapabilities(assetType);
      const followsInputDefault =
        valuationDraftIsEmpty(current.valuation) &&
        current.valuation.inputMode === currentCapabilities.defaultInputMode;
      return {
        ...current,
        assetType,
        valuation: followsInputDefault
          ? {
              ...current.valuation,
              inputMode: nextCapabilities.defaultInputMode,
            }
          : current.valuation,
        ...(followsDefault
          ? accountProfileValues(defaultProfileForAsset(assetType))
          : {}),
      };
    });
  };

  const close = () => {
    if (pending) return;
    setDraft(initialDraft(account));
    setAdvancedOpen(false);
    onOpenChange(false);
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) return;
    const reviewInterval =
      draft.reviewInterval === "never"
        ? null
        : (Number(draft.reviewInterval) as 7 | 30 | 90 | 180);
    await onSubmit({
      name: draft.name.trim(),
      institution: draft.institution.trim() || null,
      kind: draft.kind,
      wrapper: draft.wrapper,
      tracking_mode: draft.trackingMode,
      default_currency: draft.currency,
      notes: draft.notes.trim() || null,
      aggregate_asset_type: aggregate ? draft.assetType : null,
      review_interval_days: aggregate ? reviewInterval : undefined,
      initial_valuation:
        aggregate && !editing ? valuationPayload(draft.valuation) : null,
    });
    setDraft(initialDraft(account));
    setAdvancedOpen(false);
    onOpenChange(false);
  }

  const title = editing
    ? aggregate
      ? t("assets.editHolding")
      : t("assets.editAccount")
    : t("assets.addAccount");

  const nameField = (
    <div className="space-y-2">
      <Label htmlFor="asset-account-name">{t("assets.accountName")}</Label>
      <Input
        id="asset-account-name"
        value={draft.name}
        onChange={(event) => update("name", event.target.value)}
        placeholder={
          aggregate
            ? t("assets.accountNamePlaceholder")
            : t("assets.detailedAccountNamePlaceholder")
        }
        autoFocus
      />
    </div>
  );

  const assetTypeField = (
    <div className="space-y-2">
      <Label>{t("assets.assetType")}</Label>
      <Select value={draft.assetType} onValueChange={updateAssetType}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ASSET_TYPES.map((type) => (
            <SelectItem
              key={type}
              value={type}
              indicatorPosition="right"
            >
              {t(assetTypeKey(type))}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const institutionField = (
    <div className="space-y-2">
      <Label htmlFor="asset-institution">{t("assets.institution")}</Label>
      <Input
        id="asset-institution"
        value={draft.institution}
        onChange={(event) => update("institution", event.target.value)}
        placeholder={t("common.optional")}
      />
    </div>
  );

  const accountProfileField = (
    <div className="space-y-2">
      <Label>{t("assets.accountProfile")}</Label>
      <Select
        value={accountProfile(draft.kind, draft.wrapper)}
        onValueChange={(value: AccountProfile) => updateProfile(value)}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ACCOUNT_PROFILES.map((profile) => (
            <SelectItem
              key={profile.value}
              value={profile.value}
              indicatorPosition="right"
            >
              {t(profile.key)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const currencyField = (
    <div className="space-y-2">
      <Label>{t("assets.currency")}</Label>
      <CurrencyCombobox
        value={draft.currency}
        onChange={(value) => update("currency", value)}
      />
    </div>
  );

  const notesField = (
    <div className="space-y-2">
      <Label htmlFor="asset-account-notes">{t("assets.notes")}</Label>
      <textarea
        id="asset-account-notes"
        value={draft.notes}
        onChange={(event) => update("notes", event.target.value)}
        className="min-h-20 w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        placeholder={t("common.optional")}
      />
    </div>
  );

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
    >
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-hidden p-0">
        <form onSubmit={submit} className="flex max-h-[90vh] min-h-0 flex-col">
          <DialogHeader className="shrink-0 px-6 pt-6">
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription className="sr-only">
              {editing
                ? t("assets.editAccountDescription")
                : t("assets.addAccountDescription")}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5 [&_[role=combobox]]:bg-muted/20 [&_button[aria-label]]:bg-muted/20 [&_input]:bg-muted/20 [&_textarea]:bg-muted/20">
            {!editing ? (
              <div className="space-y-2 pb-3">
                <Label>{t("assets.trackingMode")}</Label>
                <div
                  className="grid gap-3 sm:grid-cols-2"
                  role="radiogroup"
                  aria-label={t("assets.trackingMode")}
                >
                  <TrackingModeCard
                    checked={aggregate}
                    icon={WalletCards}
                    title={t("assets.trackingMode.aggregate")}
                    description={t("assets.trackingMode.aggregateHint")}
                    onClick={() => update("trackingMode", "aggregate")}
                  />
                  <TrackingModeCard
                    checked={!aggregate}
                    icon={Layers3}
                    title={t("assets.trackingMode.detailed")}
                    description={t("assets.trackingMode.detailedHint")}
                    onClick={() => update("trackingMode", "detailed")}
                  />
                </div>
              </div>
            ) : null}

            {aggregate && !editing ? (
              <div className="grid lg:grid-cols-[minmax(15rem,0.75fr)_minmax(0,1.25fr)]">
                <section className="space-y-4 lg:pr-10">
                  <h3 className="text-base font-semibold">
                    {t("assets.basicData")}
                  </h3>
                  {nameField}
                  {assetTypeField}
                </section>
                <section className="mt-7 space-y-4 border-t pt-7 lg:mt-0 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
                  <h3 className="text-base font-semibold">
                    {t("assets.currentValue")}
                  </h3>
                  <AssetValuationFields
                    value={draft.valuation}
                    onChange={(value) => update("valuation", value)}
                    currency={draft.currency}
                    currencyControl={currencyField}
                    showGrowth={false}
                  />
                </section>
              </div>
            ) : !aggregate ? (
              <div className="grid lg:grid-cols-2">
                <section className="space-y-4 lg:pr-10">
                  <h3 className="text-base font-semibold">
                    {t("assets.basicData")}
                  </h3>
                  {nameField}
                  {institutionField}
                </section>
                <section className="mt-7 space-y-4 border-t pt-7 lg:mt-0 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
                  <h3 className="text-base font-semibold">
                    {t("assets.accountSettings")}
                  </h3>
                  <div
                    className={cn(
                      "grid gap-4",
                      !editing && "sm:grid-cols-2",
                    )}
                  >
                    {accountProfileField}
                    {!editing ? currencyField : null}
                  </div>
                  {notesField}
                </section>
              </div>
            ) : (
              <section className="space-y-4">
                <h3 className="text-base font-semibold">
                  {t("assets.basicData")}
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  {nameField}
                  {assetTypeField}
                </div>
              </section>
            )}

            {aggregate ? (
              <div>
                <button
                  type="button"
                  className="flex w-full items-center justify-between py-2 text-left text-base font-semibold text-foreground transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  aria-expanded={advancedOpen}
                  aria-controls="asset-additional-settings"
                  onClick={() => setAdvancedOpen((current) => !current)}
                >
                  <span>{t("assets.moreSettings")}</span>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 transition-transform",
                      advancedOpen && "rotate-180",
                    )}
                  />
                </button>
                {advancedOpen ? (
                  <div
                    id="asset-additional-settings"
                    className="space-y-5 pb-1 pt-2"
                  >
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      {showsAccountProfile ? (
                        <>
                          <div className="space-y-2">
                            <Label>{t("assets.accountProfile")}</Label>
                            <Select
                              value={accountProfile(
                                draft.kind,
                                draft.wrapper,
                              )}
                              onValueChange={(value: AccountProfile) =>
                                updateProfile(value)
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {AGGREGATE_ACCOUNT_PROFILES.map((profile) => (
                                  <SelectItem
                                    key={profile.value}
                                    value={profile.value}
                                    indicatorPosition="right"
                                  >
                                    {profile.value === "other"
                                      ? t("assets.profile.none")
                                      : t(profile.key)}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          {institutionField}
                        </>
                      ) : null}
                      <div className="space-y-2">
                        <Label>{t("assets.reviewInterval")}</Label>
                        <Select
                          value={draft.reviewInterval}
                          onValueChange={(value) =>
                            update("reviewInterval", value)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {REVIEW_INTERVAL_OPTIONS.map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                                indicatorPosition="right"
                              >
                                {t(option.key)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    {!editing &&
                    (capabilities.supportsFixedGrowth ||
                      draft.valuation.growthMode !== "none") ? (
                      <AssetGrowthFields
                        value={draft.valuation}
                        onChange={(value) => update("valuation", value)}
                      />
                    ) : null}
                    {notesField}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          <DialogFooter className="shrink-0 border-t px-6 py-4">
            <Button
              type="button"
              variant="outline"
              onClick={close}
              disabled={pending}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!canSave || pending}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {editing
                ? t("common.save")
                : aggregate
                  ? t("common.add")
                  : t("assets.createAccount")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
