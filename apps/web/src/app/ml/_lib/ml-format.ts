import type { MlDashboard } from "@/lib/api";
import type { TranslationKey } from "@/lib/i18n";
import type { Formatters } from "@/lib/formatters";

type TFn = (key: TranslationKey, vars?: Record<string, string | number>) => string;

export function formatDateTime(
  value: string | null,
  formatter: Formatters["formatDateTime"],
): string {
  if (!value) return "—";
  return formatter(value);
}

export function percent(
  value: number | null | undefined,
  formatter: Formatters["formatPercent"],
): string {
  return typeof value === "number" ? formatter(value) : "—";
}

export function estimatorName(value: string | null | undefined): string {
  switch (value) {
    case "logreg":
      return "Logistic Regression";
    case "linear_svc_calibrated":
      return "Calibrated LinearSVC";
    default:
      return value ?? "—";
  }
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
    case "best_holdout_result":
      return t("ml.recommendation.reason.best_holdout_result");
    case "no_promotable_candidate":
      return t("ml.recommendation.reason.noPromotableCandidate");
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
