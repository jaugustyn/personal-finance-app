"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { invalidateTransactionData, queryKeys } from "@/lib/query-keys";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import {
  pageTabsListClassName,
  pageTabTriggerClassName,
} from "@/components/page-tabs";
import { CardGridSkeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FeedbackQualityCard } from "./_components/feedback-quality-card";
import { ModelLifecycleCard } from "./_components/model-lifecycle-card";
import { ModelComparisonCard } from "./_components/model-comparison-card";
import { ModelStatusSummary } from "./_components/model-status-summary";
import { NextStepCard } from "./_components/next-step-card";
import { TechnicalDetailsCard } from "./_components/technical-details-card";
import { TrainingSummaryCard } from "./_components/training-summary-card";

const RETRAIN_TOAST_ID = "ml-retrain-status";

export default function MlPage() {
  const { t } = useT();
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
  const recommendation = data?.recommendation;
  const isRetraining =
    retrain.isPending ||
    ["queued", "running"].includes(retrainStatus.data?.status ?? "");

  return (
    <div className="space-y-5">
      <PageHeader title={t("ml.title")} />

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
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
          <TabsList className={pageTabsListClassName}>
            <TabsTrigger
              value="overview"
              className={pageTabTriggerClassName}
            >
              {t("ml.tab.overview")}
            </TabsTrigger>
            <TabsTrigger
              value="technical"
              className={pageTabTriggerClassName}
            >
              {t("ml.tab.technical")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <NextStepCard
              data={data}
              isRetraining={isRetraining}
              isReclassifying={reclassify.isPending}
              isActivating={activate.isPending}
              onRetrain={() => retrain.mutate({})}
              onReclassify={() => reclassify.mutate()}
              onActivate={(modelId) => activate.mutate(modelId)}
            />

            <ModelStatusSummary data={data} />

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
