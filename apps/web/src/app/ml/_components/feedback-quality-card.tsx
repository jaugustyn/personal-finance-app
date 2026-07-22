import { ChevronDown, MessageSquareCheck } from "lucide-react";

import { tCategory, useFormatters, useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { numberFromRecord, percent } from "../_lib/ml-format";

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
  const suggestionTotal = numberFromRecord(quality, "suggestion_feedback_total") ?? 0;
  const acceptanceRate = numberFromRecord(quality, "acceptance_rate");
  const sinceTraining = quality.scope === "since_last_training";

  return (
    <details className="group overflow-hidden rounded-lg border bg-card shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <div className="flex items-center gap-2 font-medium text-foreground">
            <MessageSquareCheck className="h-4 w-4 text-muted-foreground" />
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
            <h3 className="text-sm font-medium text-foreground">
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
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="border-b bg-muted/30 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">
                    {t("ml.feedback.suggestion")}
                  </th>
                  <th className="px-3 py-2 font-medium">
                    {t("ml.feedback.userDecision")}
                  </th>
                  <th className="px-3 py-2 text-right font-medium">
                    {t("ml.feedback.count")}
                  </th>
                  <th className="px-3 py-2 font-medium">
                    {t("ml.feedback.example")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {hotspots.slice(0, 5).map((row, index) => {
                  const predicted = String(row.predicted_category ?? "—");
                  const final = row.final_category
                    ? String(row.final_category)
                    : null;
                  const merchant = row.merchant ? String(row.merchant) : "—";
                  const count =
                    typeof row.count === "number"
                      ? row.count
                      : Number(row.count ?? 0);
                  return (
                    <tr key={`${predicted}-${final}-${merchant}-${index}`}>
                      <td className="px-3 py-2.5 font-medium text-foreground">
                        {tCategory(t, predicted)}
                      </td>
                      <td className="px-3 py-2.5 text-foreground">
                        {final
                          ? tCategory(t, final)
                          : t("ml.feedback.rejectedLabel")}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-foreground">
                        {formatNumber(count)}
                      </td>
                      <td className="max-w-[280px] truncate px-3 py-2.5 text-muted-foreground">
                        {merchant}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
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
