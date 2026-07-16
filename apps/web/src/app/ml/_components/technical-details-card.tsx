import { ChevronDown, Settings2 } from "lucide-react";

import type { MlDashboard } from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  estimatorName,
  numberFromRecord,
  percent,
} from "../_lib/ml-format";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function TechnicalDetailsCard({ data }: { data: MlDashboard }) {
  const { t } = useT();
  const training = data.latest_training;
  if (!training.exists || Object.keys(training.metrics).length === 0) return null;

  const candidate =
    data.model_comparison.find((row) => row.is_recommended) ??
    data.model_comparison[0];
  const time = asRecord(training.metrics.time);
  const merchant = asRecord(training.metrics.merchant);
  const technicalGate = asRecord(training.gates.technical);
  const threshold = numberFromRecord(
    training.confidence_policy,
    "default_threshold",
  );
  const p99 = numberFromRecord(training.metrics, "p99_ms");
  const unsupported = Object.entries(training.unsupported_classes);

  return (
    <details className="group overflow-hidden rounded-lg border bg-card shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-foreground">
            {t("ml.details.title")}
          </span>
        </div>
        <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>

      <div className="space-y-5 border-t px-4 py-4">
        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("ml.details.validation")}
          </h3>
          <div className="grid gap-3 lg:grid-cols-2">
            <ValidationSlice
              title={t("ml.details.timeHoldout")}
              metrics={time}
            />
            <ValidationSlice
              title={t("ml.details.merchantHoldout")}
              metrics={merchant}
            />
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <DetailItem
            label={t("ml.details.estimator")}
            value={estimatorName(candidate?.estimator)}
          />
          <DetailItem
            label={t("ml.details.runtimeThreshold")}
            value={threshold == null ? "—" : threshold.toFixed(2)}
          />
          <DetailItem
            label={t("ml.details.latency")}
            value={p99 == null ? "—" : `${p99.toFixed(1)} ms`}
          />
          <DetailItem
            label={t("ml.details.gates")}
            value={
              technicalGate.passed === true
                ? t("ml.details.passed")
                : t("ml.details.failed")
            }
            positive={technicalGate.passed === true}
          />
        </section>

        <section className="grid gap-4 border-t pt-4 lg:grid-cols-2">
          <div>
            <div className="text-xs text-muted-foreground">
              {t("ml.details.supportedClasses")}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {training.supported_classes.map((category) => (
                <Badge key={category} variant="secondary">
                  {tCategory(t, category)}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              {t("ml.details.unsupportedClasses")}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {unsupported.length > 0 ? (
                unsupported.map(([category, count]) => (
                  <Badge key={category} variant="outline">
                    {tCategory(t, category)}: {formatNumber(count)}
                  </Badge>
                ))
              ) : (
                <span className="text-sm text-muted-foreground">—</span>
              )}
            </div>
          </div>
        </section>

        <section className="flex flex-wrap gap-x-5 gap-y-2 border-t pt-4 text-xs text-muted-foreground">
          <span>
            {t("ml.details.trainSize")}: {formatNumber(training.split_counts.train ?? 0)}
          </span>
          <span>
            {t("ml.details.duration")}: {formatDuration(training.duration_seconds)}
          </span>
          <span>
            {t("ml.details.dataVersion")}: {shortId(training.dataset_fingerprint)}
          </span>
          <span>
            {t("ml.details.job")}: {shortId(training.job_id)}
          </span>
        </section>
      </div>
    </details>
  );
}

function ValidationSlice({
  title,
  metrics,
}: {
  title: string;
  metrics: Record<string, unknown>;
}) {
  const { t } = useT();
  return (
    <div className="rounded-md border bg-muted/10 p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-foreground">{title}</span>
        <span className="text-xs tabular-nums text-muted-foreground">
          n={formatNumber(numberFromRecord(metrics, "n") ?? 0)}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        <SliceMetric
          label={t("ml.comparison.macro")}
          value={percent(numberFromRecord(metrics, "macro_f1"))}
        />
        <SliceMetric
          label={t("ml.comparison.weighted")}
          value={percent(numberFromRecord(metrics, "weighted_f1"))}
        />
        <SliceMetric
          label={t("ml.comparison.coverage")}
          value={percent(numberFromRecord(metrics, "coverage"))}
        />
        <SliceMetric
          label={t("ml.comparison.accuracy")}
          value={percent(numberFromRecord(metrics, "accuracy_on_covered"))}
        />
      </div>
    </div>
  );
}

function SliceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums text-foreground">
        {value}
      </div>
    </div>
  );
}

function DetailItem({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="rounded-md border px-3 py-2.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`mt-1 text-sm font-medium ${positive ? "text-positive" : "text-foreground"}`}
      >
        {value}
      </div>
    </div>
  );
}

function formatDuration(value: number | null): string {
  if (value == null) return "—";
  if (value < 60) return `${Math.round(value)} s`;
  return `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
}

function shortId(value: string | null): string {
  if (!value) return "—";
  return value.length > 14 ? `${value.slice(0, 12)}…` : value;
}
