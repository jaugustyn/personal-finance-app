"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  api,
  type MlDashboard,
  type MlModelComparison,
  type MlModelRecommendation,
} from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { cn, formatNumber, formatPercent } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Database,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pl-PL", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function percent(value: number | null | undefined): string {
  return typeof value === "number" ? formatPercent(value) : "—";
}

function numberFromRecord(
  data: Record<string, unknown>,
  key: string,
): number | null {
  const value = data[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readinessLabel(level: string, t: ReturnType<typeof useT>["t"]) {
  switch (level) {
    case "insufficient":
      return t("ml.readiness.insufficient");
    case "minimum":
      return t("ml.readiness.minimum");
    case "good":
      return t("ml.readiness.good");
    case "thesis_ready":
      return t("ml.readiness.thesis_ready");
    default:
      return t("ml.readiness.unknown");
  }
}

function readinessVariant(level: string) {
  if (level === "good" || level === "thesis_ready") return "success" as const;
  if (level === "minimum") return "warning" as const;
  return "destructive" as const;
}

function statusLabel(data: MlDashboard, t: ReturnType<typeof useT>["t"]) {
  if (data.status.load_error) return t("ml.status.error");
  if (!data.status.exists) return t("ml.status.missing");
  if (data.status.missing_categories.length > 0) return t("ml.status.outdated");
  return t("ml.status.ready");
}

function statusVariant(data: MlDashboard) {
  if (data.status.load_error || !data.status.exists) return "destructive" as const;
  if (data.status.missing_categories.length > 0) return "warning" as const;
  return "success" as const;
}

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
        {hint ? (
          <div className="mt-1 truncate text-xs text-muted-foreground">{hint}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function recommendationReason(
  code: string,
  t: ReturnType<typeof useT>["t"],
): string {
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

function ModelComparisonCard({
  rows,
  recommendation,
}: {
  rows: MlModelComparison[];
  recommendation: MlModelRecommendation;
}) {
  const { t } = useT();
  const hasRows = rows.length > 0;
  const columns: DataTableColumn<MlModelComparison>[] = [
    {
      id: "model",
      header: t("ml.comparison.model"),
      sortValue: (row) => row.rank ?? 999,
      className: "font-medium",
      cell: (row) => (
        <>
          <span className="mr-2 text-xs text-muted-foreground">
            #{row.rank}
          </span>
          {row.estimator}
        </>
      ),
    },
    {
      id: "features",
      header: t("ml.comparison.features"),
      sortValue: (row) => row.feature_set,
      className: "text-muted-foreground",
      cell: (row) => row.feature_set,
    },
    {
      id: "macro",
      header: t("ml.comparison.macro"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.macro_f1,
      cell: (row) => percent(row.macro_f1),
    },
    {
      id: "weighted",
      header: t("ml.comparison.weighted"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.weighted_f1,
      cell: (row) => percent(row.weighted_f1),
    },
    {
      id: "stability",
      header: t("ml.comparison.stability"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.stability_score,
      cell: (row) => percent(row.stability_score),
    },
    {
      id: "coverage",
      header: t("ml.comparison.coverage"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.coverage_at_055,
      cell: (row) => percent(row.coverage_at_055),
    },
    {
      id: "accuracy",
      header: t("ml.comparison.accuracy"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.accuracy_at_055,
      cell: (row) => percent(row.accuracy_at_055),
    },
    {
      id: "status",
      header: t("ml.comparison.status"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1">
          {row.is_recommended ? (
            <Badge variant="success">{t("ml.comparison.recommended")}</Badge>
          ) : null}
          {row.is_current ? (
            <Badge variant="secondary">{t("ml.comparison.current")}</Badge>
          ) : null}
          {row.skipped ? (
            <Badge variant="warning">{t("ml.comparison.skipped")}</Badge>
          ) : null}
        </div>
      ),
    },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <Sparkles className="h-4 w-4 text-primary" />
          {t("ml.comparison.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t("ml.comparison.help")}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border bg-muted/20 p-3">
          <div className="space-y-2">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-xs font-medium text-muted-foreground">
                  {t("ml.comparison.nextTraining")}
                </div>
                <Badge variant="info">{t("ml.comparison.recommended")}</Badge>
              </div>
              <div className="mt-1 font-medium">
                {recommendation.estimator} · {recommendation.feature_set}
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              {recommendationReason(recommendation.reason_code, t)}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("ml.comparison.activeModelNote")}
            </p>
          </div>
        </div>

        {hasRows ? (
          <DataTable
            columns={columns}
            data={rows}
            rowKey={(row) => `${row.feature_set}-${row.estimator}`}
            initialSort={{ id: "model", dir: "asc" }}
            tableClassName="min-w-[840px]"
            getRowClassName={(row) =>
              row.is_recommended ? "bg-primary/5" : undefined
            }
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("ml.comparison.noReport")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function FeedbackQualityCard({
  quality,
  hotspots,
}: {
  quality: Record<string, unknown>;
  hotspots: Record<string, unknown>[];
}) {
  const { t } = useT();
  const accepted = numberFromRecord(quality, "accepted_suggestions") ?? 0;
  const rejected = numberFromRecord(quality, "rejected_suggestions") ?? 0;
  const manual = numberFromRecord(quality, "manual_category_events") ?? 0;
  const acceptanceRate = numberFromRecord(quality, "acceptance_rate");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-foreground">
          {t("ml.feedback.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.feedback.accepted")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(accepted)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.feedback.rejected")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(rejected)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.feedback.manual")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(manual)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.feedback.acceptanceRate")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {percent(acceptanceRate)}
            </div>
          </div>
        </div>
        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {t("ml.feedback.hotspots")}
          </div>
          {hotspots.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("ml.feedback.noHotspots")}
            </p>
          ) : (
            <div className="space-y-2">
              {hotspots.slice(0, 5).map((row, index) => {
                const predicted = String(row.predicted_category ?? "—");
                const final = row.final_category ? String(row.final_category) : null;
                const merchant = row.merchant ? String(row.merchant) : "—";
                const count =
                  typeof row.count === "number" ? row.count : Number(row.count ?? 0);
                return (
                  <div
                    key={`${predicted}-${final}-${merchant}-${index}`}
                    className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">
                        {tCategory(t, predicted)} →{" "}
                        {final ? tCategory(t, final) : t("ml.feedback.rejectedLabel")}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {merchant}
                      </div>
                    </div>
                    <Badge variant="warning">{formatNumber(count)}</Badge>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function MlPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["mlDashboard"],
    queryFn: () => api.mlDashboard(),
  });

  const retrain = useMutation({
    mutationFn: (params: { estimator: string; feature_set: string }) =>
      api.retrainClassifier(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mlDashboard"] });
      toast.success(t("ml.retrainStarted"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const reclassify = useMutation({
    mutationFn: () => api.reclassifyTransactions(),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["mlDashboard"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      toast.success(t("ml.reclassifyDone", { n: result.updated }));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const data = query.data;
  const readiness = data?.readiness;
  const status = data?.status;
  const best = status?.best_model;
  const recommendation = data?.recommendation;
  const retrainParams = {
    estimator: recommendation?.estimator ?? "linear_svc_calibrated",
    feature_set: recommendation?.feature_set ?? "feature_v2",
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("ml.title")}
        description={t("ml.subtitle")}
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => reclassify.mutate()}
              disabled={reclassify.isPending}
            >
              {reclassify.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              {t("ml.reclassify")}
            </Button>
            <Button
              onClick={() => retrain.mutate(retrainParams)}
              disabled={retrain.isPending}
            >
              {retrain.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <BrainCircuit className="h-4 w-4" />
              )}
              {t("ml.retrain")}
            </Button>
          </>
        }
      />

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : query.isError || !data || !readiness || !status ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label={t("ml.kpi.model")}
              value={status.exists ? t("ml.status.ready") : t("ml.status.missing")}
              hint={formatDateTime(status.updated_at)}
            />
            <MetricCard
              label={t("ml.kpi.labels")}
              value={formatNumber(readiness.total_labelled)}
              hint={readinessLabel(readiness.level, t)}
            />
            <MetricCard
              label={t("ml.kpi.classes")}
              value={`${status.classes.length}/${status.known_categories.length}`}
              hint={
                status.missing_categories.length > 0
                  ? status.missing_categories.map((cat) => tCategory(t, cat)).join(", ")
                  : t("ml.classes.known")
              }
            />
            <MetricCard
              label={t("ml.kpi.macro")}
              value={percent(best?.macro_f1)}
              hint={best?.model ?? undefined}
            />
          </div>

          <ModelComparisonCard
            rows={data.model_comparison}
            recommendation={data.recommendation}
          />

          <FeedbackQualityCard
            quality={data.feedback_quality}
            hotspots={data.confusion_hotspots}
          />

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  {status.load_error || !status.exists ? (
                    <AlertTriangle className="h-4 w-4 text-destructive" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-positive" />
                  )}
                  {t("ml.status.title")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Badge variant={statusVariant(data)}>
                  {statusLabel(data, t)}
                </Badge>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">
                      {t("ml.meta.estimator")}
                    </dt>
                    <dd className="font-medium">{status.estimator ?? "—"}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">
                      {t("ml.meta.featureSet")}
                    </dt>
                    <dd className="font-medium">{status.feature_set ?? "—"}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">
                      {t("ml.meta.updated")}
                    </dt>
                    <dd className="font-medium">
                      {formatDateTime(status.updated_at)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">
                      {t("ml.meta.report")}
                    </dt>
                    <dd className="max-w-40 truncate font-medium">
                      {status.report_path ?? "—"}
                    </dd>
                  </div>
                </dl>
                {status.load_error ? (
                  <p className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                    {status.load_error}
                  </p>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-foreground">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  {t("ml.readiness.title")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Badge variant={readinessVariant(readiness.level)}>
                  {readinessLabel(readiness.level, t)}
                </Badge>
                <p className="text-sm text-muted-foreground">
                  {t("ml.readiness.help")}
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>{t("ml.categories.minimum", {
                      n: readiness.minimum_total,
                    })}</span>
                    <span className="font-medium tabular-nums">
                      {formatNumber(readiness.total_labelled)}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{
                        width: `${Math.min(
                          100,
                          (readiness.total_labelled /
                            Math.max(1, readiness.ideal_total)) *
                            100,
                        )}%`,
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{formatNumber(readiness.minimum_total)}</span>
                    <span>{formatNumber(readiness.recommended_total)}</span>
                    <span>{formatNumber(readiness.ideal_total)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base text-foreground">
                  {t("ml.report.title")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {best ? (
                  <>
                    <div>
                      <div className="text-xs text-muted-foreground">
                        {t("ml.report.best")}
                      </div>
                      <div className="mt-1 text-lg font-semibold">
                        {best.model ?? "—"}
                      </div>
                    </div>
                    <dl className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">
                          {t("ml.kpi.macro")}
                        </dt>
                        <dd className="font-medium">{percent(best.macro_f1)}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">
                          Weighted-F1
                        </dt>
                        <dd className="font-medium">{percent(best.weighted_f1)}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">
                          {t("ml.report.coverage")}
                        </dt>
                        <dd className="font-medium">
                          {percent(best.coverage_at_055)}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">
                          {t("ml.report.accuracy")}
                        </dt>
                        <dd className="font-medium">
                          {percent(best.accuracy_at_055)}
                        </dd>
                      </div>
                    </dl>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {t("ml.report.none")}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-foreground">
                  {t("ml.categories.title")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {status.known_categories.map((category) => {
                    const count = readiness.category_counts[category] ?? 0;
                    const target = readiness.recommended_per_category;
                    const minimum = readiness.minimum_per_category;
                    const width = Math.min(100, (count / Math.max(1, target)) * 100);
                    const underMinimum = count < minimum;
                    return (
                      <div key={category} className="space-y-1">
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <span className="font-medium">
                            {tCategory(t, category)}
                          </span>
                          <span
                            className={cn(
                              "tabular-nums",
                              underMinimum
                                ? "text-destructive"
                                : "text-muted-foreground",
                            )}
                          >
                            {t("ml.categories.confirmed", { n: count })}
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              underMinimum ? "bg-destructive" : "bg-primary",
                            )}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-[11px] text-muted-foreground">
                          <span>{t("ml.categories.minimum", { n: minimum })}</span>
                          <span>
                            {t("ml.categories.recommended", { n: target })}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-foreground">
                    {t("ml.classes.title")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ClassList
                    title={t("ml.classes.known")}
                    values={status.classes}
                    variant="secondary"
                  />
                  <ClassList
                    title={t("ml.classes.missing")}
                    values={status.missing_categories}
                    variant="destructive"
                  />
                  <ClassList
                    title={t("ml.classes.extra")}
                    values={status.extra_classes}
                    variant="outline"
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-foreground">
                    {t("ml.workflow.title")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ol className="space-y-2 text-sm text-muted-foreground">
                    <li>1. {t("ml.workflow.labels")}</li>
                    <li>2. {t("ml.workflow.balance")}</li>
                    <li>3. {t("ml.workflow.train")}</li>
                    <li>4. {t("ml.workflow.predict")}</li>
                  </ol>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline" size="sm">
                      <Link href="/review">{t("ml.openReview")}</Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href="/transactions">{t("ml.openTransactions")}</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ClassList({
  title,
  values,
  variant,
}: {
  title: string;
  values: string[];
  variant: "secondary" | "destructive" | "outline";
}) {
  const { t } = useT();
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      {values.length === 0 ? (
        <span className="text-sm text-muted-foreground">—</span>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <Badge key={value} variant={variant}>
              {tCategory(t, value)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
