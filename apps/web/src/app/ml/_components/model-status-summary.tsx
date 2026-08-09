import { Download, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, type MlDashboard } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import {
  estimatorName,
  formatDateTime,
  percent,
  statusLabel,
  statusVariant,
} from "../_lib/ml-format";

export function ModelStatusSummary({ data }: { data: MlDashboard }) {
  const { t } = useT();
  const { formatDateTime: formatTimestamp, formatPercent } = useFormatters();
  const { status } = data;

  return (
    <section className="space-y-3">
      <div className="flex min-h-9 flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">
          {t("ml.status.title")}
        </h2>
        <Badge variant={statusVariant(data)}>{statusLabel(data, t)}</Badge>
      </div>

      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="grid divide-y sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <StatusItem
            label={t("ml.meta.estimator")}
            value={estimatorName(status.estimator)}
            hint={status.exists ? undefined : t("ml.status.missing")}
          />
          <StatusItem
            label={t("ml.kpi.macro")}
            value={percent(status.best_model?.macro_f1, formatPercent)}
            hint={status.best_model?.model ?? undefined}
          />
          <StatusItem
            label={t("ml.meta.updated")}
            value={formatDateTime(status.updated_at, formatTimestamp)}
          />
        </div>

        {status.report_path ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
            <span className="text-sm text-muted-foreground">
              {t("ml.status.activeReport")}
            </span>
            <div className="flex flex-wrap gap-2">
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
          <p className="border-t border-destructive/30 bg-destructive/10 px-4 py-3 text-xs text-destructive">
            {status.load_error}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function StatusItem({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-sm font-medium tabular-nums text-foreground">
        {value}
      </div>
      {hint ? (
        <div className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}
