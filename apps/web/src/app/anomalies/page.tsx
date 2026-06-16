"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type Anomaly, type Direction } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { FilterField, FilterPanel } from "@/components/filter-panel";
import { PageHeader } from "@/components/page-header";
import { Money } from "@/components/money";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/utils";
import { useT, tCategory } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";
import { HelpCircle } from "lucide-react";

type AnomalyMode = "review" | "suspicious" | "all";
type AnomalyFeedbackAction = "relevant" | "not_relevant" | "ignore_merchant";

function priorityVariant(
  priority: number,
): "default" | "warning" | "destructive" {
  if (priority >= 0.75) return "destructive";
  if (priority >= 0.5) return "warning";
  return "default";
}

function anomalyTypeLabel(type: string, t: ReturnType<typeof useT>["t"]): string {
  switch (type) {
    case "suspicious":
      return t("anomalies.type.suspicious");
    case "unexpected_large":
      return t("anomalies.type.unexpectedLarge");
    case "merchant_amount_outlier":
      return t("anomalies.type.merchantAmountOutlier");
    case "data_quality":
      return t("anomalies.type.dataQuality");
    case "model_only":
      return t("anomalies.type.modelOnly");
    default:
      return type;
  }
}

function anomalyTypeHint(type: string, t: ReturnType<typeof useT>["t"]): string {
  switch (type) {
    case "suspicious":
      return t("anomalies.typeHint.suspicious");
    case "unexpected_large":
      return t("anomalies.typeHint.unexpectedLarge");
    case "merchant_amount_outlier":
      return t("anomalies.typeHint.merchantAmountOutlier");
    case "data_quality":
      return t("anomalies.typeHint.dataQuality");
    case "model_only":
      return t("anomalies.typeHint.modelOnly");
    default:
      return type;
  }
}

function feedbackToast(
  action: AnomalyFeedbackAction,
  t: ReturnType<typeof useT>["t"],
) {
  switch (action) {
    case "relevant":
      toast.info(t("anomalies.feedbackSaved.relevant"), {
        description: t("anomalies.feedbackEffect.relevant"),
      });
      break;
    case "not_relevant":
      toast.warning(t("anomalies.feedbackSaved.notRelevant"), {
        description: t("anomalies.feedbackEffect.notRelevant"),
      });
      break;
    case "ignore_merchant":
      toast.success(t("anomalies.feedbackSaved.ignoreMerchant"), {
        description: t("anomalies.feedbackEffect.ignoreMerchant"),
      });
      break;
  }
}

export default function AnomaliesPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const [direction, setDirection] = useLocalStorageState<Direction>(
    "finance.anomalies.direction",
    "debit",
  );
  const [mode, setMode] = useLocalStorageState<AnomalyMode>(
    "finance.anomalies.mode",
    "review",
  );
  const [includeModelOnly, setIncludeModelOnly] = useLocalStorageState(
    "finance.anomalies.includeModelOnly",
    false,
  );
  const [feedbackById, setFeedbackById] = useState<
    Record<number, AnomalyFeedbackAction>
  >({});
  const query = useQuery({
    queryKey: ["anomalies", direction, mode, includeModelOnly],
    queryFn: () =>
      api.anomalies({
        direction,
        mode,
        include_model_only: includeModelOnly,
      }),
  });
  const feedback = useMutation({
    mutationFn: ({
      transactionId,
      action,
    }: {
      transactionId: number;
      action: AnomalyFeedbackAction;
    }) => api.recordAnomalyFeedback(transactionId, action),
    onSuccess: (_result, variables) => {
      setFeedbackById((current) => ({
        ...current,
        [variables.transactionId]: variables.action,
      }));
      qc.invalidateQueries({ queryKey: ["anomalies"] });
      qc.invalidateQueries({ queryKey: ["mlDashboard"] });
      feedbackToast(variables.action, t);
    },
    onError: () => toast.error(t("toast.error")),
  });
  const columns: DataTableColumn<Anomaly>[] = [
    {
      id: "booking_date",
      header: t("transactions.column.date"),
      sortValue: (a) => a.booking_date,
      className: "text-muted-foreground",
      cell: (a) => formatDate(a.booking_date),
    },
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (a) => a.merchant || a.title,
      className: "font-medium",
      cell: (a) => (
        <>
          <Link
            href={transactionsHref({ search: a.merchant || a.title })}
            className="text-primary underline-offset-4 hover:underline"
            title={t("anomalies.openTransaction")}
          >
            {a.merchant || a.title}
          </Link>
          {a.reasons.length > 0 ? (
            <div className="mt-1 max-w-md text-xs font-normal text-muted-foreground">
              {a.reasons.join(", ")}
            </div>
          ) : null}
          {a.is_recurring_merchant ? (
            <div className="mt-1 text-xs font-normal text-muted-foreground">
              {t("anomalies.recurring", {
                count: a.merchant_occurrences,
              })}
            </div>
          ) : null}
        </>
      ),
    },
    {
      id: "type",
      header: (
        <span className="inline-flex items-center gap-1.5">
          {t("anomalies.type")}
          <Tooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
            </TooltipTrigger>
            <TooltipContent className="max-w-72">
              {t("anomalies.typeHelp")}
            </TooltipContent>
          </Tooltip>
        </span>
      ),
      sortValue: (a) => anomalyTypeLabel(a.anomaly_type, t),
      cell: (a) => (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="outline" className="cursor-help">
              {anomalyTypeLabel(a.anomaly_type, t)}
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-72">
            {anomalyTypeHint(a.anomaly_type, t)}
          </TooltipContent>
        </Tooltip>
      ),
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (a) => a.category ?? "",
      cell: (a) =>
        a.category ? (
          <Badge variant="secondary">{tCategory(t, a.category)}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "priority",
      header: t("anomalies.priority"),
      sortValue: (a) => a.priority_score,
      cell: (a) => (
        <Badge variant={priorityVariant(a.priority_score)}>
          {(a.priority_score * 100).toFixed(0)}%
        </Badge>
      ),
    },
    {
      id: "amount",
      header: t("transactions.column.amount"),
      align: "right",
      sortValue: (a) => Number(a.amount),
      cell: (a) => <Money amount={Number(a.amount)} direction={a.direction} />,
    },
    {
      id: "actions",
      header: t("common.actions"),
      align: "right",
      cell: (a) => {
        const recordedFeedback = feedbackById[a.id] ?? a.feedback_status;
        return (
          <div className="flex flex-wrap justify-end gap-1">
            {recordedFeedback ? (
              <Badge
                variant={
                  recordedFeedback === "not_relevant"
                    ? "warning"
                    : recordedFeedback === "ignore_merchant"
                      ? "success"
                      : "info"
                }
              >
                {recordedFeedback === "relevant"
                  ? t("anomalies.feedback.recordedRelevant")
                  : recordedFeedback === "not_relevant"
                    ? t("anomalies.feedback.recordedNotRelevant")
                    : t("anomalies.feedback.recordedIgnored")}
              </Badge>
            ) : (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={feedback.isPending}
                  onClick={() =>
                    feedback.mutate({
                      transactionId: a.id,
                      action: "relevant",
                    })
                  }
                >
                  {t("anomalies.feedback.relevant")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={feedback.isPending}
                  onClick={() =>
                    feedback.mutate({
                      transactionId: a.id,
                      action: "not_relevant",
                    })
                  }
                >
                  {t("anomalies.feedback.notRelevant")}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={feedback.isPending}
                  onClick={() =>
                    feedback.mutate({
                      transactionId: a.id,
                      action: "ignore_merchant",
                    })
                  }
                >
                  {t("anomalies.feedback.ignoreMerchant")}
                </Button>
              </>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("anomalies.title")}
        description={t("anomalies.subtitle")}
      />

      <FilterPanel gridClassName="md:grid-cols-3 xl:grid-cols-3">
        <FilterField label={t("transactions.filterDirection")}>
          <Select
            value={direction}
            onValueChange={(v) => setDirection(v as Direction)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="debit">
                {t("transactions.filterDirection.debit")}
              </SelectItem>
              <SelectItem value="credit">
                {t("transactions.filterDirection.credit")}
              </SelectItem>
              <SelectItem value="all">
                {t("transactions.filterDirection.all")}
              </SelectItem>
            </SelectContent>
          </Select>
        </FilterField>
        <FilterField label={t("anomalies.mode")}>
          <Select value={mode} onValueChange={(v) => setMode(v as AnomalyMode)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="review">{t("anomalies.mode.review")}</SelectItem>
              <SelectItem value="suspicious">
                {t("anomalies.mode.suspicious")}
              </SelectItem>
              <SelectItem value="all">{t("anomalies.mode.all")}</SelectItem>
            </SelectContent>
          </Select>
        </FilterField>
        <FilterField label={t("anomalies.modelOnly")}>
          <Select
            value={includeModelOnly ? "show" : "hide"}
            onValueChange={(v) => setIncludeModelOnly(v === "show")}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hide">{t("anomalies.modelOnly.hide")}</SelectItem>
              <SelectItem value="show">{t("anomalies.modelOnly.show")}</SelectItem>
            </SelectContent>
          </Select>
        </FilterField>
      </FilterPanel>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("anomalies.top")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TooltipProvider delayDuration={150}>
            <DataTable
              columns={columns}
              data={query.data}
              rowKey={(a) => a.id}
              isLoading={query.isLoading}
              emptyTitle={t("anomalies.empty")}
              initialSort={{ id: "priority", dir: "desc" }}
            />
          </TooltipProvider>
        </CardContent>
      </Card>
    </div>
  );
}
