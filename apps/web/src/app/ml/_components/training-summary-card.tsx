import { Download, FileText } from "lucide-react";

import type { MlDashboard } from "@/lib/api";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  estimatorName,
  formatDateTime,
  percent,
} from "../_lib/ml-format";

export function TrainingSummaryCard({
  data,
  onOpenPanel,
}: {
  data: MlDashboard;
  onOpenPanel: () => void;
}) {
  const { t } = useT();
  const training = data.latest_training;
  const candidate =
    data.model_comparison.find((row) => row.is_recommended) ??
    data.model_comparison[0];

  if (!training.exists) {
    return (
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-muted/30 text-muted-foreground">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <div className="font-medium text-foreground">
                {t("ml.report.emptyTitle")}
              </div>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {t("ml.report.emptyDescription")}
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={onOpenPanel}>
            {t("ml.report.openPanel")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t("ml.report.lastTraining")}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-foreground">
                {estimatorName(candidate?.estimator)}
              </h2>
              {candidate?.is_recommended ? (
                <Badge variant="success">{t("ml.comparison.recommended")}</Badge>
              ) : (
                <Badge variant="warning">
                  {t("ml.comparison.noRecommendation")}
                </Badge>
              )}
              {candidate?.is_current ? (
                <Badge variant="secondary">{t("ml.comparison.current")}</Badge>
              ) : null}
            </div>
          </div>
          {training.report_available ? (
            <Button asChild variant="outline" size="sm">
              <a href={api.mlLatestTrainingReportFileUrl()}>
                <Download className="h-3.5 w-3.5" />
                {t("ml.report.download")}
              </a>
            </Button>
          ) : null}
        </div>

        <div className="grid gap-x-6 gap-y-3 border-y py-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="text-xs text-muted-foreground">
              {t("ml.report.weakestMacro")}
            </div>
            <div className="mt-0.5 text-2xl font-semibold tabular-nums text-primary">
              {percent(candidate?.stability_score)}
            </div>
          </div>
          <SummaryMetric
            label={t("ml.report.meanMacro")}
            value={percent(candidate?.macro_f1)}
          />
          <SummaryMetric
            label={t("ml.report.coverage")}
            value={percent(candidate?.coverage_at_055)}
          />
          <SummaryMetric
            label={t("ml.report.accuracy")}
            value={percent(candidate?.accuracy_at_055)}
          />
        </div>

        <div className="flex flex-wrap gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>
            {t("ml.report.labelCount", {
              count: formatNumber(training.label_count ?? 0),
            })}
          </span>
          <span aria-hidden="true">·</span>
          <span>
            {t("ml.report.classCount", {
              count: formatNumber(training.supported_classes.length),
            })}
          </span>
          <span aria-hidden="true">·</span>
          <span>{formatDateTime(training.finished_at)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
        {value}
      </div>
    </div>
  );
}
