"use client";

import { CheckCircle2, CircleAlert, XCircle } from "lucide-react";
import type { ImportQualityReport } from "@/lib/api";
import { useT, type TranslationKey } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";

export function ImportQualityPanel({ report }: { report: ImportQualityReport }) {
  const { t } = useT();
  const hasBlockingIssues = report.blocking_issues > 0;
  const hasWarnings = report.warnings > 0;
  const statusLabel =
    hasBlockingIssues
      ? t("imports.quality.statusIssues")
      : hasWarnings
        ? t("imports.quality.warnings")
      : t("imports.quality.statusOk");

  return (
    <div className="rounded-md border bg-muted/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{t("imports.quality.title")}</h3>
        <div aria-label={statusLabel} title={statusLabel}>
          {hasBlockingIssues ? (
            <XCircle className="h-7 w-7 fill-destructive/10 text-destructive" />
          ) : hasWarnings ? (
            <CircleAlert className="h-7 w-7 fill-warning/15 text-warning" />
          ) : (
            <CheckCircle2 className="h-7 w-7 fill-positive/10 text-positive" />
          )}
        </div>
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
    <div className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-md border bg-background p-3 text-center">
      <div className="flex min-h-10 items-center text-xs leading-5 text-muted-foreground">
        {label}
      </div>
      <Badge variant={variant} className="text-sm tabular-nums">
        {value}
      </Badge>
    </div>
  );
}

function importQualityIssueKey(code: string): TranslationKey {
  return `imports.quality.issue.${code}` as TranslationKey;
}
