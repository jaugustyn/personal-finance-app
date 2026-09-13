"use client";

import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";
import { HelpTooltip } from "@/components/help-tooltip";
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
  SelectGroup,
  SelectSeparator,
  SelectLabel,
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
import { cn } from "@/lib/utils";
import {
  pageTabTriggerClassName,
  pageTabsListClassName,
} from "@/components/page-tabs";
import { useT, type TranslationKey } from "@/lib/i18n";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ASSET_TYPE_GROUPS,
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
  type ValuationDraft,
} from "./asset-valuation-fields";

type AccountProfile =
  AssetAccountKind | Exclude<AssetAccountWrapper, "standard">;

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
  currency: string;
  assetType: AssetType;
  reviewInterval: string;
  notes: string;
  valuation: ValuationDraft;
}

function initialDraft(
  account?: AssetAccount | null,
  mode: AssetTrackingMode = "aggregate",
): AccountDraft {
  const assetType = account?.aggregate_asset_type ?? "savings_account";
  return {
    name: account?.name ?? "",
    institution: account?.institution ?? "",
    kind: account?.kind ?? (mode === "detailed" ? "brokerage" : "bank"),
    wrapper: account?.wrapper ?? "standard",
    currency: account?.default_currency ?? "PLN",
    assetType,
    reviewInterval: account
      ? account.review_interval_days == null
        ? "never"
        : String(account.review_interval_days)
      : "never",
    notes: account?.notes ?? "",
    valuation: emptyValuationDraft(),
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

export function AssetAccountDialog({
  account,
  mode,
  open,
  onOpenChange,
  onSubmit,
  pending,
}: {
  account?: AssetAccount | null;
  mode: AssetTrackingMode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: AssetAccountInput) => Promise<void>;
  pending: boolean;
}) {
  const { t } = useT();
  const editing = Boolean(account);
  const [draft, setDraft] = useState<AccountDraft>(() =>
    initialDraft(account, mode),
  );
  const [tab, setTab] = useState("basic");
  const aggregate = (account?.tracking_mode ?? mode) === "aggregate";
  const capabilities = assetTypeCapabilities(draft.assetType);
  const showsAccountProfile = aggregate && capabilities.supportsAccountProfile;
  const showGrowth = !editing && aggregate;
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
      return {
        ...current,
        assetType,
        ...(followsDefault
          ? accountProfileValues(defaultProfileForAsset(assetType))
          : {}),
      };
    });
  };

  const close = () => {
    if (pending) return;
    setDraft(initialDraft(account, mode));
    setTab("basic");
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
      tracking_mode: aggregate ? "aggregate" : "detailed",
      default_currency: draft.currency,
      notes: draft.notes.trim() || null,
      aggregate_asset_type: aggregate ? draft.assetType : null,
      review_interval_days: aggregate ? reviewInterval : undefined,
      initial_valuation:
        aggregate && !editing ? valuationPayload(draft.valuation) : null,
    });
    setDraft(initialDraft(account, mode));
    setTab("basic");
    onOpenChange(false);
  }

  const title = editing
    ? aggregate
      ? t("assets.editHolding")
      : t("assets.editAccount")
    : aggregate
      ? t("assets.addHolding")
      : t("assets.addPortfolio");

  const nameField = (
    <div className="flex flex-col gap-2">
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
      />
    </div>
  );

  const assetTypeField = (
    <div key="asset-type" className="flex flex-col gap-2">
      <Label>{t("assets.assetType")}</Label>
      <Select value={draft.assetType} onValueChange={updateAssetType}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ASSET_TYPE_GROUPS.map((group, index) => (
            <SelectGroup key={group.label}>
              {index > 0 ? <SelectSeparator /> : null}
              <SelectLabel className="px-2 py-2 text-sm font-medium text-muted-foreground">
                {t(group.label)}
              </SelectLabel>
              {group.types.map((type) => (
                <SelectItem key={type} value={type} indicatorPosition="right">
                  {t(assetTypeKey(type))}
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const institutionField = (
    <div className="flex flex-col gap-2">
      <Label htmlFor="asset-institution">{t("assets.institution")}</Label>
      <Input
        id="asset-institution"
        value={draft.institution}
        onChange={(event) => update("institution", event.target.value)}
        placeholder={t("assets.institutionPlaceholder")}
      />
    </div>
  );

  const accountProfileField = (
    <div key="account-profile" className="flex flex-col gap-2">
      {aggregate ? (
        <Label>{t("assets.accountProfile")}</Label>
      ) : (
        <HelpTooltip content={t("assets.portfolioSetupHint")}>
          <Label>{t("assets.accountProfile")}</Label>
        </HelpTooltip>
      )}
      <Select
        value={accountProfile(draft.kind, draft.wrapper)}
        onValueChange={(value: AccountProfile) => updateProfile(value)}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(aggregate ? AGGREGATE_ACCOUNT_PROFILES : ACCOUNT_PROFILES).map(
            (profile) => (
              <SelectItem
                key={profile.value}
                value={profile.value}
                indicatorPosition="right"
              >
                {aggregate && profile.value === "other"
                  ? t("assets.profile.none")
                  : t(profile.key)}
              </SelectItem>
            ),
          )}
        </SelectContent>
      </Select>
    </div>
  );

  const currencyField = (
    <div className="flex flex-col gap-2">
      <Label>{t("assets.currency")}</Label>
      <CurrencyCombobox
        value={draft.currency}
        onChange={(value) => update("currency", value)}
      />
    </div>
  );

  const notesField = (
    <div className="flex flex-col gap-2">
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
      <DialogContent
        className={cn(
          "max-h-[90dvh] overflow-hidden p-0 md:top-[10dvh] md:translate-y-0",
          aggregate ? "max-w-5xl" : "max-w-3xl",
        )}
      >
        <form onSubmit={submit} className="flex max-h-[80dvh] min-h-0 flex-col">
          <DialogHeader className="shrink-0 px-6 pt-8 sm:px-8">
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription className="sr-only">
              {editing
                ? t("assets.editAccountDescription")
                : t("assets.addAccountDescription")}
            </DialogDescription>
          </DialogHeader>

          {!aggregate ? (
            <div className="grid min-h-0 gap-6 overflow-y-auto px-6 py-8 sm:px-8 md:grid-cols-2">
              {nameField}
              {accountProfileField}
              {institutionField}
              {currencyField}
              <div className="md:col-span-2">{notesField}</div>
            </div>
          ) : (
            <Tabs
              value={tab}
              onValueChange={setTab}
              className="flex min-h-0 flex-1 flex-col"
            >
              <div className="shrink-0 px-6 pt-6 sm:px-8">
                <TabsList
                  className={cn(
                    pageTabsListClassName,
                    "h-auto w-full justify-start rounded-none bg-transparent p-0",
                  )}
                  aria-label={t("assets.accountSettings")}
                >
                  <TabsTrigger
                    value="basic"
                    className={pageTabTriggerClassName}
                  >
                    {t("assets.basicData")}
                  </TabsTrigger>
                  <TabsTrigger
                    value="details"
                    className={pageTabTriggerClassName}
                  >
                    {t("assets.detailsTab")}
                    {!editing && draft.valuation.growthMode !== "none" ? (
                      <span
                        className="h-1.5 w-1.5 rounded-full bg-primary"
                        aria-label={t("assets.growth.fixedRate")}
                      />
                    ) : null}
                  </TabsTrigger>
                </TabsList>
              </div>
              <div className="grid min-h-0 flex-1 overflow-y-auto px-6 py-8 sm:px-8">
                <TabsContent value="basic" className="space-y-6">
                  {editing ? (
                    <div className="grid gap-6 md:grid-cols-2">
                      {nameField}
                      {aggregate ? assetTypeField : accountProfileField}
                    </div>
                  ) : (
                    <div className="grid gap-8 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
                      <div className="space-y-6">
                        {nameField}
                        {aggregate ? assetTypeField : accountProfileField}
                      </div>
                      <div className="space-y-8 md:border-l md:pl-8">
                        {aggregate ? (
                          <AssetValuationFields
                            value={draft.valuation}
                            onChange={(value) => update("valuation", value)}
                            currency={draft.currency}
                            currencyControl={currencyField}
                            showInputMode={
                              capabilities.defaultInputMode === "unit_price"
                            }
                            showGrowth={false}
                          />
                        ) : (
                          <>{currencyField}</>
                        )}
                      </div>
                    </div>
                  )}
                </TabsContent>
                <TabsContent
                  value="details"
                  className="grid content-start gap-6 data-[state=inactive]:hidden md:grid-cols-2"
                >
                  <div className="space-y-6">
                    {institutionField}
                    {showsAccountProfile ? accountProfileField : null}
                  </div>
                  <div className="space-y-6">
                    {aggregate ? (
                      <div className="flex flex-col gap-2">
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
                    ) : null}
                    {notesField}
                  </div>
                  {showGrowth ? (
                    <div className="border-t pt-6 md:col-span-2">
                      <AssetGrowthFields
                        value={draft.valuation}
                        onChange={(value) => update("valuation", value)}
                      />
                    </div>
                  ) : null}
                </TabsContent>
              </div>
            </Tabs>
          )}

          <DialogFooter className="shrink-0 border-t px-6 py-5 sm:px-8">
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
