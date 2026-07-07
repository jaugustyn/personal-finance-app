import type { MlDashboard } from "@/lib/api";
import type { TranslationKey } from "@/lib/i18n";
import { formatPercent } from "@/lib/utils";

type TFn = (key: TranslationKey, vars?: Record<string, string | number>) => string;

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pl-PL", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function percent(value: number | null | undefined): string {
  return typeof value === "number" ? formatPercent(value) : "—";
}

export function numberFromRecord(
  data: Record<string, unknown>,
  key: string,
): number | null {
  const value = data[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function statusLabel(data: MlDashboard, t: TFn): string {
  if (data.status.load_error) return t("ml.status.error");
  if (!data.status.exists) return t("ml.status.missing");
  if (data.retrain_signal.retrain_recommended) return t("ml.status.outdated");
  return t("ml.status.ready");
}

export function statusVariant(data: MlDashboard) {
  if (data.status.load_error || !data.status.exists) return "destructive" as const;
  if (data.retrain_signal.retrain_recommended) return "warning" as const;
  return "success" as const;
}

export function recommendationReason(code: string, t: TFn): string {
  switch (code) {
    case "best_calibrated_macro_f1":
      return t("ml.recommendation.reason.best_calibrated_macro_f1");
    case "prefer_calibrated_close":
      return t("ml.recommendation.reason.prefer_calibrated_close");
    case "best_macro_f1":
      return t("ml.recommendation.reason.best_macro_f1");
    case "no_report":
      return t("ml.recommendation.reason.no_report");
    default:
      return code;
  }
}

export function retrainReasonLabel(code: string, t: TFn): string {
  switch (code) {
    case "label_growth_since_training":
      return t("ml.retrainSignal.reason.labelGrowth");
    case "feedback_since_training":
      return t("ml.retrainSignal.reason.feedback");
    case "high_rejection_rate":
      return t("ml.retrainSignal.reason.rejectionRate");
    default:
      return code;
  }
}
