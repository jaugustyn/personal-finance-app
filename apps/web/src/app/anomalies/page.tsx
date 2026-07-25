"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type Anomaly } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Money } from "@/components/money";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useFormatters, useT, tCategory } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import {
  storedValueOneOf,
  useLocalStorageState,
} from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";
import { invalidateAnomalyData, queryKeys } from "@/lib/query-keys";
import { MoreHorizontal } from "lucide-react";

type AnomalyFeedbackAction = "relevant" | "not_relevant" | "restore";
type AnomalyReviewState = "pending" | "reviewed";
const isAnomalyReviewState = storedValueOneOf<AnomalyReviewState>([
  "pending",
  "reviewed",
]);

function priorityVariant(
  priority: number,
): "secondary" | "warning" | "destructive" {
  if (priority >= 0.75) return "destructive";
  if (priority >= 0.5) return "warning";
  return "secondary";
}

function priorityLabel(
  priority: number,
  t: ReturnType<typeof useT>["t"],
): string {
  if (priority >= 0.75) return t("anomalies.priority.high");
  if (priority >= 0.5) return t("anomalies.priority.medium");
  return t("anomalies.priority.standard");
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

function anomalyReasonLabel(
  reason: string,
  t: ReturnType<typeof useT>["t"],
): string {
  switch (reason) {
    case "amount-outlier":
      return t("anomalies.reason.amountOutlier");
    case "merchant-amount-outlier":
      return t("anomalies.reason.merchantAmountOutlier");
    case "new-merchant-large-debit":
      return t("anomalies.reason.newMerchantLargeDebit");
    case "missing-merchant-large":
      return t("anomalies.reason.missingMerchantLarge");
    case "missing-category-large":
      return t("anomalies.reason.missingCategoryLarge");
    case "isolation-forest":
      return t("anomalies.reason.modelPattern");
    default:
      return reason.replaceAll("-", " ");
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
    case "restore":
      toast.success(t("anomalies.feedbackSaved.restored"), {
        description: t("anomalies.feedbackEffect.restored"),
      });
      break;
  }
}

export default function AnomaliesPage() {
  const { t } = useT();
  const { formatCurrency, formatDate, formatDateTime } = useFormatters();
  const qc = useQueryClient();
  const [reviewState, setReviewState] = useLocalStorageState<AnomalyReviewState>(
    "finance.anomalies.reviewState",
    "pending",
    { validate: isAnomalyReviewState },
  );
  const query = useQuery({
    queryKey: queryKeys.anomalies.list({
      direction: "all",
      reviewState,
    }),
    queryFn: () =>
      api.anomalies({
        direction: "all",
        review_state: reviewState,
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
      void invalidateAnomalyData(qc);
      feedbackToast(variables.action, t);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const columns: DataTableColumn<Anomaly>[] = [
    {
      id: "booking_date",
      header: t("transactions.column.date"),
      headerClassName: "w-28",
      sortValue: (a) => a.booking_date,
      className: "text-muted-foreground",
      cell: (a) => formatDate(a.booking_date),
    },
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      headerClassName: "w-64",
      sortValue: (a) => a.merchant_display || a.merchant || a.title,
      className: "font-medium",
      cell: (a) => (
        <div className="min-w-60">
          <Link
            href={transactionsHref({
              search: a.merchant || a.title,
              date_from: a.booking_date,
              date_to: a.booking_date,
            })}
            className="text-primary underline-offset-4 hover:underline"
            title={t("anomalies.openTransaction")}
          >
            {a.merchant_display || a.merchant || a.title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 font-normal">
            {a.category ? (
              <Badge variant="secondary">{tCategory(t, a.category)}</Badge>
            ) : null}
            {a.is_recurring_merchant ? (
              <span className="text-xs text-muted-foreground">
                {t("anomalies.recurring", {
                  count: a.merchant_occurrences,
                })}
              </span>
            ) : null}
          </div>
        </div>
      ),
    },
    {
      id: "reason",
      header: t("anomalies.reason"),
      headerClassName: "min-w-80",
      sortValue: (a) =>
        a.anomaly_type ? anomalyTypeLabel(a.anomaly_type, t) : "",
      cell: (a) => (
        <div className="max-w-[38rem] space-y-1">
          {a.currently_detected && a.anomaly_type ? (
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
          ) : (
            <Badge variant="secondary">
              {t("anomalies.noLongerDetected")}
            </Badge>
          )}
          {a.reason_codes.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {a.reason_codes
                .map((reason) => anomalyReasonLabel(reason, t))
                .join(", ")}
            </p>
          ) : null}
          {a.merchant_occurrences >= 4 && a.merchant_median_amount > 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("anomalies.merchantTypicalAmount", {
                amount: formatCurrency(
                  a.merchant_median_amount,
                  a.base_currency,
                ),
              })}
            </p>
          ) : null}
        </div>
      ),
    },
    {
      id: "priority",
      header: (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="cursor-help">{t("anomalies.priority")}</span>
          </TooltipTrigger>
          <TooltipContent className="max-w-72">
            {t("anomalies.priorityHelp")}
          </TooltipContent>
        </Tooltip>
      ),
      headerClassName: "w-28",
      align: "center",
      sortValue: (a) => a.priority_score,
      cell: (a) =>
        a.priority_score == null ? (
          <span className="text-muted-foreground">–</span>
        ) : (
          <Badge variant={priorityVariant(a.priority_score)}>
            {priorityLabel(a.priority_score, t)}
          </Badge>
        ),
    },
    {
      id: "amount",
      header: t("transactions.column.amount"),
      headerClassName: "w-40",
      align: "right",
      sortValue: (a) => Number(a.amount),
      cell: (a) => (
        <Money
          amount={Number(a.amount)}
          currency={a.base_currency}
          direction={a.direction}
        />
      ),
    },
    {
      id: "assessment",
      header: t("anomalies.decision"),
      headerClassName: reviewState === "pending" ? "w-60" : "w-72",
      align: "center",
      sortValue:
        reviewState === "reviewed"
          ? (a) => (a.reviewed_at ? new Date(a.reviewed_at).getTime() : null)
          : undefined,
      cell: (a) => {
        if (reviewState === "reviewed") {
          return (
            <div className="flex items-center justify-center gap-2">
              <div className="text-right">
                <Badge
                  variant={
                    a.review_status === "relevant" ? "warning" : "secondary"
                  }
                >
                  {a.review_status === "relevant"
                    ? t("anomalies.assessment.unusual")
                    : t("anomalies.assessment.normal")}
                </Badge>
                {a.reviewed_at ? (
                  <div className="mt-1 text-xs text-muted-foreground">
                    {formatDateTime(a.reviewed_at)}
                  </div>
                ) : null}
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    disabled={feedback.isPending}
                    aria-label={t("anomalies.moreActions")}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {a.review_status !== "relevant" ? (
                    <DropdownMenuItem
                      onSelect={() =>
                        feedback.mutate({
                          transactionId: a.id,
                          action: "relevant",
                        })
                      }
                    >
                      {t("anomalies.action.markUnusual")}
                    </DropdownMenuItem>
                  ) : null}
                  {a.review_status !== "not_relevant" ? (
                    <DropdownMenuItem
                      onSelect={() =>
                        feedback.mutate({
                          transactionId: a.id,
                          action: "not_relevant",
                        })
                      }
                    >
                      {t("anomalies.action.markNormal")}
                    </DropdownMenuItem>
                  ) : null}
                  <DropdownMenuItem
                    onSelect={() =>
                      feedback.mutate({
                        transactionId: a.id,
                        action: "restore",
                      })
                    }
                  >
                    {t("anomalies.action.restore")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        }
        return (
          <div className="flex flex-nowrap justify-center gap-2">
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
              {t("anomalies.assessment.unusual")}
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
              {t("anomalies.assessment.normal")}
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader title={t("anomalies.title")} />

      <nav
        className="flex max-w-full overflow-x-auto border-b"
        aria-label={t("anomalies.title")}
      >
        {(["pending", "reviewed"] as const).map((state) => {
          const active = reviewState === state;
          const count =
            state === "pending"
              ? query.data?.pending_total
              : query.data?.reviewed_total;
          return (
            <button
              key={state}
              type="button"
              onClick={() => setReviewState(state)}
              className={`inline-flex h-11 shrink-0 items-center gap-2 border-b-2 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${
                active
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
              }`}
            >
              {state === "pending"
                ? t("anomalies.tab.pending")
                : t("anomalies.tab.reviewed")}
              {count !== undefined ? (
                <Badge
                  variant="muted"
                  className={
                    active
                      ? "bg-primary/10 px-1.5 text-[10px] tabular-nums text-primary ring-1 ring-primary/15"
                      : "px-1.5 text-[10px] tabular-nums"
                  }
                >
                  {count}
                </Badge>
              ) : null}
            </button>
          );
        })}
      </nav>

      <section>
        {query.isError ? (
          <ErrorState
            title={t("anomalies.error")}
            onRetry={() => void query.refetch()}
          />
        ) : (
          <TooltipProvider delayDuration={150}>
            <DataTable
              key={reviewState}
              columns={columns}
              data={query.data?.items}
              rowKey={(a) => a.id}
              isLoading={query.isLoading}
              emptyTitle={
                reviewState === "pending"
                  ? t("anomalies.empty")
                  : t("anomalies.reviewedEmpty")
              }
              initialSort={
                reviewState === "pending"
                  ? { id: "priority", dir: "desc" }
                  : { id: "assessment", dir: "desc" }
              }
              pagination={{ mode: "client" }}
              tableClassName="min-w-[72rem] [&_td]:px-4 [&_th]:px-4"
            />
          </TooltipProvider>
        )}
      </section>
    </div>
  );
}
