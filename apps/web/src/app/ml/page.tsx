"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { invalidateTransactionData, queryKeys } from "@/lib/query-keys";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
} from "lucide-react";
import { FeedbackQualityCard } from "./_components/feedback-quality-card";
import { MetricCard } from "./_components/metric-card";
import { ModelLifecycleCard } from "./_components/model-lifecycle-card";
import { ModelComparisonCard } from "./_components/model-comparison-card";
import { NextStepCard } from "./_components/next-step-card";
import { TechnicalDetailsCard } from "./_components/technical-details-card";
import { TrainingSummaryCard } from "./_components/training-summary-card";
import {
  formatDateTime,
  percent,
  statusLabel,
  statusVariant,
} from "./_lib/ml-format";

const RETRAIN_TOAST_ID = "ml-retrain-status";

export default function MlPage() {
  const { t } = useT();
  const { formatDateTime: formatTimestamp, formatPercent } = useFormatters();
  const [activeTab, setActiveTab] = useState("overview");
  const qc = useQueryClient();
  const lastRetrainStatusRef = useRef<string | null>(null);
  const query = useQuery({
    queryKey: queryKeys.ml.dashboard,
    queryFn: () => api.mlDashboard(),
  });
  const retrainStatus = useQuery({
    queryKey: queryKeys.ml.retrainStatus,
    queryFn: () => api.retrainStatus(),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 2500
        : false,
  });
  const currentRetrainStatus = retrainStatus.data?.status ?? "idle";

  useEffect(() => {
    const previousStatus = lastRetrainStatusRef.current;
    const message = retrainStatus.data?.message;

    if (["queued", "running"].includes(currentRetrainStatus)) {
      if (!previousStatus || !["queued", "running"].includes(previousStatus)) {
        toast.loading(t("ml.retrainRunning"), { id: RETRAIN_TOAST_ID });
      }
      lastRetrainStatusRef.current = currentRetrainStatus;
      return;
    }

    if (previousStatus && ["queued", "running"].includes(previousStatus)) {
      if (currentRetrainStatus === "completed") {
        toast.success(t("ml.retrainDone"), { id: RETRAIN_TOAST_ID });
        void qc.invalidateQueries({ queryKey: queryKeys.ml.all });
      } else if (["aborted", "interrupted"].includes(currentRetrainStatus)) {
        toast.error(message ?? t("ml.retrainAborted"), { id: RETRAIN_TOAST_ID });
      } else if (currentRetrainStatus === "failed") {
        toast.error(
          retrainStatus.data?.error ?? message ?? t("ml.retrainFailed"),
          { id: RETRAIN_TOAST_ID },
        );
      } else {
        toast.dismiss(RETRAIN_TOAST_ID);
      }
    }

    lastRetrainStatusRef.current = currentRetrainStatus;
  }, [
    currentRetrainStatus,
    qc,
    retrainStatus.data?.error,
    retrainStatus.data?.message,
    t,
  ]);

  const retrain = useMutation({
    mutationFn: (params: {
      estimator?: string;
      feature_set?: string;
    }) =>
      api.retrainClassifier(params),
    onSuccess: () => {
      lastRetrainStatusRef.current = "running";
      toast.loading(t("ml.retrainRunning"), { id: RETRAIN_TOAST_ID });
      void qc.invalidateQueries({ queryKey: queryKeys.ml.all });
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const reclassify = useMutation({
    mutationFn: () => api.reclassifyTransactions(),
    onSuccess: (result) => {
      void invalidateTransactionData(qc);
      toast.success(t("ml.reclassifyDone", { n: result.updated }));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const activate = useMutation({
    mutationFn: (modelId: string) => api.activateModelVersion(modelId),
    onSuccess: () => {
      toast.success(t("ml.next.activateDone"));
      void qc.invalidateQueries({ queryKey: queryKeys.ml.all });
    },
    onError: (error) => showErrorToast(error, t("ml.next.activateFailed")),
  });

  const data = query.data;
  const status = data?.status;
  const best = status?.best_model;
  const recommendation = data?.recommendation;
  const isRetraining =
    retrain.isPending ||
    ["queued", "running"].includes(retrainStatus.data?.status ?? "");
  const showModelStatusBadge = Boolean(
    data &&
      status &&
      (status.load_error ||
        !status.exists ||
        data.retrain_signal.retrain_recommended),
  );

  return (
    <div className="space-y-5">
      <PageHeader title={t("ml.title")} description={t("ml.subtitle")} />

      {retrainStatus.isError ? (
        <ErrorState
          variant="compact"
          onRetry={() => void retrainStatus.refetch()}
        />
      ) : null}

      {query.isLoading ? (
        <CardGridSkeleton />
      ) : query.isError || !data || !status || !recommendation ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="h-9 items-stretch justify-start divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card p-0">
            <TabsTrigger
              value="overview"
              className="h-full rounded-none py-0 focus-visible:z-10 focus-visible:ring-inset data-[state=active]:bg-accent-soft data-[state=active]:text-accent-soft-foreground data-[state=active]:shadow-none"
            >
              {t("ml.tab.overview")}
            </TabsTrigger>
            <TabsTrigger
              value="technical"
              className="h-full rounded-none py-0 focus-visible:z-10 focus-visible:ring-inset data-[state=active]:bg-accent-soft data-[state=active]:text-accent-soft-foreground data-[state=active]:shadow-none"
            >
              {t("ml.tab.technical")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-3">
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
                      value={formatDateTime(status.updated_at, formatTimestamp)}
                    />
                    <MetricCard
                      label={t("ml.kpi.macro")}
                      value={percent(best?.macro_f1, formatPercent)}
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

              <NextStepCard
                data={data}
                isRetraining={isRetraining}
                isReclassifying={reclassify.isPending}
                isActivating={activate.isPending}
                onRetrain={() => retrain.mutate({})}
                onReclassify={() => reclassify.mutate()}
                onActivate={(modelId) => activate.mutate(modelId)}
              />
            </div>

            <ModelLifecycleCard />
          </TabsContent>

          <TabsContent value="technical" className="space-y-4">
            <TrainingSummaryCard
              data={data}
              onOpenPanel={() => setActiveTab("overview")}
            />

            <ModelComparisonCard rows={data.model_comparison} />

            <FeedbackQualityCard
              quality={data.feedback_quality}
              hotspots={data.confusion_hotspots}
              confirmedLabels={data.readiness.total_labelled}
            />

            <TechnicalDetailsCard data={data} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
