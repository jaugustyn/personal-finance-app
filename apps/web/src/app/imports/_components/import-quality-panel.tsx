"use client";

import { useState } from "react";
import type { ImportQualityReport } from "@/lib/api";
import { useT, type TranslationKey } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";

export function ImportQualityPanel({ report }: { report: ImportQualityReport }) {
  const { t } = useT();
  const [expanded, setExpanded] = useState(false);
  const hasBlockingIssues = report.blocking_issues > 0;
  const visibleIssues = expanded ? report.issues : report.issues.slice(0, 3);
  const hasDetails =
    report.issues.length > 3 ||
    report.issues.some((issue) => issue.sample_rows.length > 0);

  return (
    <div className="min-w-0 border-t pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{t("imports.quality.title")}</h3>
        {hasBlockingIssues ? (
          <Badge variant="destructive" className="gap-1.5">
            <span>{t("imports.quality.blocking")}</span>
            <span className="font-semibold tabular-nums">
              {report.blocking_issues}
            </span>
          </Badge>
        ) : null}
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        {t("imports.quality.validRows")}: {" "}
        <span className="font-medium tabular-nums text-foreground">
          {report.valid_rows}
        </span>
      </p>
      {report.issues.length > 0 ? (
        <div className="mt-3 space-y-2.5">
          {visibleIssues.map((issue) => (
            <div
              key={`${issue.severity}:${issue.code}`}
              className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm"
            >
              <Badge variant={issue.severity === "error" ? "destructive" : "warning"}>
                {issue.count}
              </Badge>
              <span>{t(importQualityIssueKey(issue.code))}</span>
              {expanded && issue.sample_rows.length > 0 ? (
                <span className="text-xs text-muted-foreground">
                  {t("imports.quality.rows", {
                    rows: issue.sample_rows.join(", "),
                  })}
                </span>
              ) : null}
            </div>
          ))}
          {hasDetails ? (
            <button
              type="button"
              className="text-xs font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setExpanded((current) => !current)}
            >
              {t(
                expanded
                  ? "imports.quality.lessDetails"
                  : "imports.quality.showDetails",
              )}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function importQualityIssueKey(code: string): TranslationKey {
  return `imports.quality.issue.${code}` as TranslationKey;
}
