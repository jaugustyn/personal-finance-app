"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FlaskConical,
  Loader2,
  RefreshCw,
  RotateCcw,
} from "lucide-react";

import type { MlDashboard } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  percent,
  recommendationReason,
  retrainReasonLabel,
} from "../_lib/ml-format";
import { ClassCoverageGrid } from "./class-coverage-grid";

type NextStepKind =
  | "training"
  | "labels"
  | "activate"
  | "repair"
  | "train"
  | "retrain"
  | "current";

export function NextStepCard({
  data,
  isRetraining,
  isReclassifying,
  isActivating,
  onRetrain,
  onReclassify,
  onActivate,
}: {
  data: MlDashboard;
  isRetraining: boolean;
  isReclassifying: boolean;
  isActivating: boolean;
  onRetrain: () => void;
  onReclassify: () => void;
  onActivate: (modelId: string) => void;
}) {
  const { t } = useT();
  const { formatNumber, formatPercent } = useFormatters();
  const { readiness, recommendation, retrain_signal: signal, status } = data;
  const kind = nextStepKind(data, isRetraining);
  const unsupportedClasses = Object.entries(readiness.unsupported_classes);

  const title =
    kind === "training"
      ? t("ml.retrainRunning")
      : kind === "labels"
        ? t("ml.trainingDataNotReady")
        : kind === "activate"
          ? t("ml.next.activateCandidate")
          : kind === "repair"
            ? t("ml.status.error")
            : kind === "train"
              ? t("ml.next.trainModel")
              : kind === "retrain"
                ? t("ml.retrainSignal.recommended")
                : t("ml.next.current");

  const description =
    kind === "training"
      ? t("ml.retrainRunningHint")
      : kind === "labels"
        ? t("ml.trainingDataProgress", {
            current: readiness.total_labelled,
            minimum: readiness.minimum_total,
          })
        : kind === "activate"
          ? recommendationReason(recommendation.reason_code, t)
          : kind === "repair"
            ? t("ml.next.repairHint")
            : kind === "train"
              ? t("ml.next.trainHint")
              : kind === "retrain"
                ? t("ml.next.retrainHint")
                : t("ml.next.currentHint");

  return (
    <Card>
      <CardHeader className="p-4 pb-0">
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <NextStepIcon kind={kind} />
          {t("ml.operations.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-col gap-4 rounded-md border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="font-medium text-foreground">{title}</div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {description}
            </p>
          </div>
          <div className="shrink-0">
            <NextStepAction
              kind={kind}
              candidateId={recommendation.model_id}
              isRetraining={isRetraining}
              isReclassifying={isReclassifying}
              isActivating={isActivating}
              onRetrain={onRetrain}
              onReclassify={onReclassify}
              onActivate={onActivate}
            />
          </div>
        </div>

        <div className="grid divide-y overflow-hidden rounded-md border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <SummaryMetric
            label={t("ml.readiness.labels")}
            value={`${readiness.total_labelled} / ${readiness.minimum_total}`}
          />
          <SummaryMetric
            label={t("ml.readiness.supportedClasses")}
            value={String(readiness.supported_classes.length)}
          />
          <SummaryMetric
            label={t("ml.readiness.splits")}
            value={
              readiness.split_feasible
                ? t("ml.readiness.feasible")
                : t("ml.readiness.notFeasible")
            }
          />
        </div>

        <details className="group overflow-hidden rounded-md border">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
            {t("ml.next.details")}
            <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
          </summary>
          <div className="space-y-5 border-t p-4">
            {recommendation.estimator && recommendation.feature_set ? (
              <section>
                <div className="text-xs font-medium text-muted-foreground">
                  {t("ml.comparison.nextTraining")}
                </div>
                <div className="mt-1 text-sm font-medium">
                  {recommendation.estimator} · {recommendation.feature_set}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {recommendationReason(recommendation.reason_code, t)}
                </p>
              </section>
            ) : null}

            <div className="grid gap-4 lg:grid-cols-2">
              <ClassCoverageGrid
                title={t("ml.next.supportedClasses")}
                values={readiness.supported_classes.map((category) => ({
                  category,
                  count: readiness.category_counts[category] ?? 0,
                }))}
              />
              <ClassCoverageGrid
                title={t("ml.next.unsupportedClasses")}
                values={unsupportedClasses.map(([category, count]) => ({
                  category,
                  count,
                }))}
              />
            </div>

            {status.exists ? (
              <section className="border-t pt-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t("ml.retrainSignal.title")}
                  </div>
                  {signal.retrain_recommended ? (
                    <Badge variant="warning">
                      {t("ml.retrainSignal.recommended")}
                    </Badge>
                  ) : null}
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <DetailMetric
                    label={t("ml.retrainSignal.newLabels")}
                    value={formatNumber(signal.new_labels_since_training)}
                    hint={percent(
                      signal.new_labels_since_training_ratio,
                      formatPercent,
                    )}
                  />
                  <DetailMetric
                    label={t("ml.retrainSignal.feedback")}
                    value={formatNumber(signal.feedback_events_since_model)}
                  />
                  <DetailMetric
                    label={t("ml.retrainSignal.rejectionRate")}
                    value={percent(signal.rejection_rate, formatPercent)}
                  />
                </div>
                {signal.reason_codes.length ? (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {signal.reason_codes.map((reason) => (
                      <Badge key={reason} variant="muted">
                        {retrainReasonLabel(reason, t)}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : null}
          </div>
        </details>
      </CardContent>
    </Card>
  );
}

function nextStepKind(data: MlDashboard, isRetraining: boolean): NextStepKind {
  if (isRetraining) return "training";
  if (data.status.load_error) {
    return data.readiness.training_ready ? "repair" : "labels";
  }
  if (
    data.recommendation.model_id &&
    data.recommendation.model_id !== data.status.model_version_id
  ) {
    return "activate";
  }
  if (!data.readiness.training_ready) return "labels";
  if (!data.status.exists) return "train";
  if (data.retrain_signal.retrain_recommended) return "retrain";
  return "current";
}

function NextStepIcon({ kind }: { kind: NextStepKind }) {
  if (kind === "training") {
    return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  }
  if (kind === "labels") {
    return <ClipboardCheck className="h-4 w-4 text-warning" />;
  }
  if (kind === "activate") {
    return <FlaskConical className="h-4 w-4 text-primary" />;
  }
  if (kind === "repair") {
    return <AlertTriangle className="h-4 w-4 text-destructive" />;
  }
  if (kind === "current") {
    return <CheckCircle2 className="h-4 w-4 text-positive" />;
  }
  return <RefreshCw className="h-4 w-4 text-primary" />;
}

function NextStepAction({
  kind,
  candidateId,
  isRetraining,
  isReclassifying,
  isActivating,
  onRetrain,
  onReclassify,
  onActivate,
}: {
  kind: NextStepKind;
  candidateId: string | null;
  isRetraining: boolean;
  isReclassifying: boolean;
  isActivating: boolean;
  onRetrain: () => void;
  onReclassify: () => void;
  onActivate: (modelId: string) => void;
}) {
  const { t } = useT();

  if (kind === "labels") {
    return (
      <Button asChild>
        <Link
          href={transactionsHref({
            view: "review",
            subject: "category",
          })}
        >
          <ClipboardCheck className="h-4 w-4" />
          {t("ml.next.openReview")}
        </Link>
      </Button>
    );
  }

  if (kind === "activate" && candidateId) {
    return (
      <Button onClick={() => onActivate(candidateId)} disabled={isActivating}>
        {isActivating ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <CheckCircle2 className="h-4 w-4" />
        )}
        {t("ml.next.activate")}
      </Button>
    );
  }

  if (kind === "current") {
    return (
      <Button variant="outline" onClick={onReclassify} disabled={isReclassifying}>
        {isReclassifying ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <RotateCcw className="h-4 w-4" />
        )}
        {t("ml.reclassify")}
      </Button>
    );
  }

  return (
    <Button onClick={onRetrain} disabled={isRetraining || kind === "training"}>
      {isRetraining || kind === "training" ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {isRetraining || kind === "training"
        ? t("ml.retrainRunningShort")
        : t("ml.retrain")}
    </Button>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 px-3 py-2.5 text-center">
      <div className="truncate text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-sm font-medium tabular-nums text-foreground">
        {value}
      </div>
    </div>
  );
}

function DetailMetric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium tabular-nums">{value}</div>
      {hint ? <div className="text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  );
}
