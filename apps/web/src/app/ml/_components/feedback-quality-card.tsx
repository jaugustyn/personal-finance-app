import { tCategory, useT } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { numberFromRecord, percent } from "../_lib/ml-format";

export function FeedbackQualityCard({
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
  const hasCounters =
    accepted > 0 || rejected > 0 || manual > 0 || acceptanceRate != null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-foreground">
          {t("ml.feedback.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
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
        {hasCounters ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
            <span>
              {t("ml.feedback.accepted")}:{" "}
              <span className="font-medium text-foreground">
                {formatNumber(accepted)}
              </span>
            </span>
            <span>
              {t("ml.feedback.rejected")}:{" "}
              <span className="font-medium text-foreground">
                {formatNumber(rejected)}
              </span>
            </span>
            <span>
              {t("ml.feedback.manual")}:{" "}
              <span className="font-medium text-foreground">
                {formatNumber(manual)}
              </span>
            </span>
            <span>
              {t("ml.feedback.acceptanceRate")}:{" "}
              <span className="font-medium text-foreground">
                {percent(acceptanceRate)}
              </span>
            </span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
