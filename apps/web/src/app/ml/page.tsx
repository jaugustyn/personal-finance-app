"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { tCategory, useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { cn, formatNumber } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
} from "lucide-react";
import { ClassList } from "./_components/class-list";
import { FeedbackQualityCard } from "./_components/feedback-quality-card";
import { MetricCard } from "./_components/metric-card";
import { ModelComparisonCard } from "./_components/model-comparison-card";
import { RetrainSignalCard } from "./_components/retrain-signal-card";
import {
  formatDateTime,
  percent,
  readinessLabel,
  readinessVariant,
  statusLabel,
  statusVariant,
} from "./_lib/ml-format";

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
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const reclassify = useMutation({
    mutationFn: () => api.reclassifyTransactions(),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["mlDashboard"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      toast.success(t("ml.reclassifyDone", { n: result.updated }));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
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

          <RetrainSignalCard signal={data.retrain_signal} />

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
