import { ChevronDown } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { tCategory, useFormatters, useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { numberFromRecord, percent } from "../_lib/ml-format";

interface FeedbackHotspotRow {
  id: string;
  predicted: string;
  final: string | null;
  merchant: string;
  count: number;
}

export function FeedbackQualityCard({
  quality,
  hotspots,
  confirmedLabels,
}: {
  quality: Record<string, unknown>;
  hotspots: Record<string, unknown>[];
  confirmedLabels: number;
}) {
  const { t } = useT();
  const { formatNumber, formatPercent } = useFormatters();
  const accepted = numberFromRecord(quality, "accepted_suggestions") ?? 0;
  const rejected = numberFromRecord(quality, "rejected_suggestions") ?? 0;
  const suggestionTotal =
    numberFromRecord(quality, "suggestion_feedback_total") ?? 0;
  const acceptanceRate = numberFromRecord(quality, "acceptance_rate");
  const sinceTraining = quality.scope === "since_last_training";
  const hotspotRows: FeedbackHotspotRow[] = hotspots
    .slice(0, 5)
    .map((row, index) => {
      const predicted = String(row.predicted_category ?? "—");
      const final = row.final_category ? String(row.final_category) : null;
      const merchant = row.merchant ? String(row.merchant) : "—";
      const count =
        typeof row.count === "number" ? row.count : Number(row.count ?? 0);
      return {
        id: `${predicted}-${final}-${merchant}-${index}`,
        predicted,
        final,
        merchant,
        count,
      };
    });
  const columns: DataTableColumn<FeedbackHotspotRow>[] = [
    {
      id: "suggestion",
      header: t("ml.feedback.suggestion"),
      sortValue: (row) => row.predicted,
      className: "font-medium",
      cell: (row) => tCategory(t, row.predicted),
    },
    {
      id: "decision",
      header: t("ml.feedback.userDecision"),
      sortValue: (row) => row.final ?? "",
      cell: (row) =>
        row.final
          ? tCategory(t, row.final)
          : t("ml.feedback.rejectedLabel"),
    },
    {
      id: "count",
      header: t("ml.feedback.count"),
      align: "right",
      sortValue: (row) => row.count,
      className: "tabular-nums",
      cell: (row) => formatNumber(row.count),
    },
    {
      id: "example",
      header: t("ml.feedback.example"),
      sortValue: (row) => row.merchant,
      className: "text-muted-foreground",
      cell: (row) => (
        <span className="block max-w-[280px] truncate">{row.merchant}</span>
      ),
    },
  ];

  return (
    <details className="group overflow-hidden rounded-lg border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <div className="font-medium text-foreground">
            {t("ml.feedback.title")}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
            {suggestionTotal > 0 ? (
              <>
                <span>
                  {t("ml.feedback.acceptedCount", {
                    count: formatNumber(accepted),
                  })}
                </span>
                <span aria-hidden="true">·</span>
                <span>
                  {t("ml.feedback.rejectedCount", {
                    count: formatNumber(rejected),
                  })}
                </span>
                <span aria-hidden="true">·</span>
                <span>
                  {t("ml.feedback.acceptanceShare", {
                    value: percent(acceptanceRate, formatPercent),
                  })}
                </span>
              </>
            ) : (
              <span>{t("ml.feedback.noReviewed")}</span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="hidden text-xs text-muted-foreground sm:inline">
            {sinceTraining
              ? t("ml.feedback.sinceTraining")
              : t("ml.feedback.allTime")}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
        </div>
      </summary>

      <div className="space-y-4 border-t px-4 py-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {t("ml.feedback.errorAnalysis")}
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {t("ml.feedback.reviewedCount", {
                count: formatNumber(suggestionTotal),
              })}
            </p>
          </div>
          <Badge variant="muted">
            {sinceTraining
              ? t("ml.feedback.sinceTraining")
              : t("ml.feedback.allTime")}
          </Badge>
        </div>

        {hotspots.length === 0 ? (
          <p className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
            {t("ml.feedback.noHotspots")}
          </p>
        ) : (
          <DataTable
            columns={columns}
            data={hotspotRows}
            rowKey={(row) => row.id}
            initialSort={{ id: "count", dir: "desc" }}
            tableClassName="min-w-[620px]"
          />
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-sm">
          <span className="text-muted-foreground">
            {t("ml.feedback.trainingData")}
          </span>
          <span className="font-medium text-foreground">
            {t("ml.feedback.confirmedLabels", {
              count: formatNumber(confirmedLabels),
            })}
          </span>
        </div>
      </div>
    </details>
  );
}
