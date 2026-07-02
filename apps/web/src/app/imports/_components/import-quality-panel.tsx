"use client";

import type { ImportQualityReport } from "@/lib/api";
import { useT, type TranslationKey } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";

export function ImportQualityPanel({ report }: { report: ImportQualityReport }) {
  const { t } = useT();
  const statusVariant = report.blocking_issues > 0 ? "destructive" : "success";
  const statusLabel =
    report.blocking_issues > 0
      ? t("imports.quality.statusIssues")
      : t("imports.quality.statusOk");

  return (
    <div className="rounded-md border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{t("imports.quality.title")}</h3>
        <Badge variant={statusVariant}>{statusLabel}</Badge>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <QualityMetric
          label={t("imports.quality.validRows")}
          value={report.valid_rows}
          variant="success"
        />
        <QualityMetric
          label={t("imports.quality.blocking")}
          value={report.blocking_issues}
          variant={report.blocking_issues > 0 ? "destructive" : "muted"}
        />
        <QualityMetric
          label={t("imports.quality.warnings")}
          value={report.warnings}
          variant={report.warnings > 0 ? "warning" : "muted"}
        />
      </div>
      {report.issues.length > 0 ? (
        <div className="mt-3 space-y-2">
          {report.issues.slice(0, 6).map((issue) => (
            <div
              key={`${issue.severity}:${issue.code}`}
              className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm"
            >
              <Badge variant={issue.severity === "error" ? "destructive" : "warning"}>
                {issue.count}
              </Badge>
              <span>{t(importQualityIssueKey(issue.code))}</span>
              {issue.sample_rows.length > 0 ? (
                <span className="text-xs text-muted-foreground">
                  {t("imports.quality.rows", {
                    rows: issue.sample_rows.join(", "),
                  })}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          {t("imports.quality.noIssues")}
        </p>
      )}
    </div>
  );
}

function QualityMetric({
  label,
  value,
  variant,
}: {
  label: string;
  value: number;
  variant: "success" | "warning" | "destructive" | "muted";
}) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <Badge variant={variant} className="mt-2 text-sm tabular-nums">
        {value}
      </Badge>
    </div>
  );
}

function importQualityIssueKey(code: string): TranslationKey {
  return `imports.quality.issue.${code}` as TranslationKey;
}
