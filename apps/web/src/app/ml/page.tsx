"use client";

import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { FeedbackQualityCard } from "./_components/feedback-quality-card";
import { MetricCard } from "./_components/metric-card";
import { ModelComparisonCard } from "./_components/model-comparison-card";
import { RetrainSignalCard } from "./_components/retrain-signal-card";
import {
  formatDateTime,
  percent,
  recommendationReason,
  statusLabel,
  statusVariant,
} from "./_lib/ml-format";

const RETRAIN_TOAST_ID = "ml-retrain-status";

export default function MlPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const lastRetrainStatusRef = useRef<string | null>(null);
  const query = useQuery({
    queryKey: ["mlDashboard"],
    queryFn: () => api.mlDashboard(),
  });
  const retrainStatus = useQuery({
    queryKey: ["mlRetrainStatus"],
    queryFn: () => api.retrainStatus(),
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 2500 : false,
  });
  const currentRetrainStatus = retrainStatus.data?.status ?? "idle";

  useEffect(() => {
    const previousStatus = lastRetrainStatusRef.current;
    const message = retrainStatus.data?.message;

    if (currentRetrainStatus === "running") {
      if (previousStatus !== "running") {
        toast.loading(t("ml.retrainRunning"), { id: RETRAIN_TOAST_ID });
      }
      lastRetrainStatusRef.current = currentRetrainStatus;
      return;
    }

    if (previousStatus === "running") {
      if (currentRetrainStatus === "completed") {
        toast.success(t("ml.retrainDone"), { id: RETRAIN_TOAST_ID });
        void qc.invalidateQueries({ queryKey: ["mlDashboard"] });
      } else if (currentRetrainStatus === "aborted") {
        toast.error(message ?? t("ml.retrainAborted"), { id: RETRAIN_TOAST_ID });
      } else if (currentRetrainStatus === "failed") {
        toast.error(message ?? t("ml.retrainFailed"), { id: RETRAIN_TOAST_ID });
      } else {
        toast.dismiss(RETRAIN_TOAST_ID);
      }
    }

    lastRetrainStatusRef.current = currentRetrainStatus;
  }, [currentRetrainStatus, qc, retrainStatus.data?.message, t]);

  const retrain = useMutation({
    mutationFn: (params: { estimator: string; feature_set: string }) =>
      api.retrainClassifier(params),
    onSuccess: () => {
      lastRetrainStatusRef.current = "running";
      toast.loading(t("ml.retrainRunning"), { id: RETRAIN_TOAST_ID });
      void qc.invalidateQueries({ queryKey: ["mlRetrainStatus"] });
      void qc.invalidateQueries({ queryKey: ["mlDashboard"] });
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
  const status = data?.status;
  const best = status?.best_model;
  const recommendation = data?.recommendation;
  const isRetraining =
    retrain.isPending || retrainStatus.data?.status === "running";
  const showModelStatusBadge = Boolean(
    data &&
      status &&
      (status.load_error ||
        !status.exists ||
        data.retrain_signal.retrain_recommended),
  );
  const retrainParams = {
    estimator: recommendation?.estimator ?? "linear_svc_calibrated",
    feature_set: recommendation?.feature_set ?? "feature_v2",
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("ml.title")} description={t("ml.subtitle")} />

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : query.isError || !data || !status || !recommendation ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : (
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="h-auto flex-wrap justify-start">
            <TabsTrigger value="overview">{t("ml.tab.overview")}</TabsTrigger>
            <TabsTrigger value="technical">{t("ml.tab.technical")}</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)]">
              <Card>
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <CardTitle className="flex items-center gap-2 text-base text-foreground">
                    {status.load_error || !status.exists ? (
                      <AlertTriangle className="h-4 w-4 text-destructive" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 text-positive" />
                    )}
                    {t("ml.status.title")}
                  </CardTitle>
                  {showModelStatusBadge ? (
                    <Badge variant={statusVariant(data)}>
                      {statusLabel(data, t)}
                    </Badge>
                  ) : null}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <MetricCard
                      label={t("ml.meta.estimator")}
                      value={status.estimator ?? "—"}
                      hint={status.exists ? undefined : t("ml.status.missing")}
                    />
                    <MetricCard
                      label={t("ml.meta.featureSet")}
                      value={status.feature_set ?? "—"}
                    />
                    <MetricCard
                      label={t("ml.meta.updated")}
                      value={formatDateTime(status.updated_at)}
                    />
                    <MetricCard
                      label={t("ml.kpi.macro")}
                      value={percent(best?.macro_f1)}
                      hint={best?.model ?? undefined}
                    />
                  </div>

                  {status.report_path ? (
                    <div className="flex min-h-[66px] min-w-0 flex-col gap-3 rounded-md border bg-muted/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background text-muted-foreground">
                          <FileText className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-medium text-muted-foreground">
                            {t("ml.report.training")}
                          </div>
                          <div className="mt-0.5 truncate text-sm text-foreground">
                            {status.report_path}
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button asChild variant="outline" size="sm">
                          <a
                            href={api.mlLatestReportFileUrl(false)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            {t("ml.report.open")}
                          </a>
                        </Button>
                        <Button asChild variant="outline" size="sm">
                          <a href={api.mlLatestReportFileUrl(true)}>
                            <Download className="h-3.5 w-3.5" />
                            {t("ml.report.download")}
                          </a>
                        </Button>
                      </div>
                    </div>
                  ) : null}

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
                    <BrainCircuit className="h-4 w-4 text-primary" />
                    {t("ml.operations.title")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="min-h-[104px] rounded-md border bg-muted/20 p-4">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <span>{t("ml.comparison.nextTraining")}</span>
                    </div>
                    <div className="mt-1 font-medium">
                      {recommendation.estimator} · {recommendation.feature_set}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {recommendationReason(recommendation.reason_code, t)}
                    </p>
                  </div>

                  <div className="flex min-h-[66px] flex-wrap items-start gap-2">
                    <Button
                      onClick={() => retrain.mutate(retrainParams)}
                      disabled={isRetraining}
                    >
                      {isRetraining ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      {isRetraining ? t("ml.retrainRunningShort") : t("ml.retrain")}
                    </Button>
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
                  </div>
                  {isRetraining ? (
                    <div className="flex items-start gap-2 rounded-md border border-primary/20 bg-primary/5 p-3 text-xs text-muted-foreground">
                      <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                      <span>{t("ml.retrainRunningHint")}</span>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </div>

            <RetrainSignalCard signal={data.retrain_signal} />
          </TabsContent>

          <TabsContent value="technical" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-foreground">
                  {t("ml.report.title")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {best ? (
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <MetricCard
                      label={t("ml.report.best")}
                      value={best.model ?? "—"}
                    />
                    <MetricCard
                      label={t("ml.kpi.macro")}
                      value={percent(best.macro_f1)}
                    />
                    <MetricCard
                      label={t("ml.comparison.weighted")}
                      value={percent(best.weighted_f1)}
                    />
                    <MetricCard
                      label={t("ml.report.coverage")}
                      value={percent(best.coverage_at_055)}
                    />
                    <MetricCard
                      label={t("ml.report.accuracy")}
                      value={percent(best.accuracy_at_055)}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {t("ml.report.none")}
                  </p>
                )}
              </CardContent>
            </Card>

            <FeedbackQualityCard
              quality={data.feedback_quality}
              hotspots={data.confusion_hotspots}
            />

            <ModelComparisonCard rows={data.model_comparison} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
