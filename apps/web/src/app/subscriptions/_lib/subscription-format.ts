import type { Subscription, SubscriptionPreferenceInput } from "@/lib/api";
import type { TranslationKey } from "@/lib/i18n";

export const statusTone: Record<Subscription["status"], string> = {
  active: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  new: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  price_increased: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  price_decreased: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  probably_cancelled: "border-muted bg-muted text-muted-foreground",
  paused_or_missing: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  annual_renewal: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  needs_review: "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-300",
  ignored: "border-muted bg-muted text-muted-foreground",
};

export const statusLabels: Record<Subscription["status"], TranslationKey> = {
  active: "subscriptions.status.active",
  new: "subscriptions.status.new",
  price_increased: "subscriptions.status.priceIncreased",
  price_decreased: "subscriptions.status.priceDecreased",
  probably_cancelled: "subscriptions.status.probablyCancelled",
  paused_or_missing: "subscriptions.status.pausedOrMissing",
  annual_renewal: "subscriptions.status.annualRenewal",
  needs_review: "subscriptions.status.needsReview",
  ignored: "subscriptions.status.ignored",
};

export const cadenceLabels: Record<string, TranslationKey> = {
  weekly: "subscriptions.cadence.weekly",
  biweekly: "subscriptions.cadence.biweekly",
  monthly: "subscriptions.cadence.monthly",
  yearly: "subscriptions.cadence.yearly",
  unknown: "subscriptions.cadence.unknown",
};

export type SubscriptionScope = "all" | "attention" | "active" | "hidden";
export type CadenceOverride = NonNullable<SubscriptionPreferenceInput["cadence_override"]>;

type TFn = (key: TranslationKey) => string;

export function sourceLabel(source: Subscription["source"], t: TFn): string {
  switch (source) {
    case "category":
      return t("subscriptions.source.category");
    case "confirmed":
      return t("subscriptions.source.confirmed");
    case "preference":
      return t("subscriptions.source.preference");
    case "detected":
    default:
      return t("subscriptions.source.detected");
  }
}
