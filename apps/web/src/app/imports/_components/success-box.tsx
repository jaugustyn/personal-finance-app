"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";

import type { ImportSummary } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { transactionsHref } from "@/lib/transaction-links";
import { Button } from "@/components/ui/button";

export function SuccessBox({ summary }: { summary: ImportSummary }) {
  const { t } = useT();
  const missingFxCount =
    summary.quality_report.issues.find((issue) => issue.code === "missing_fx_rate")
      ?.count ?? 0;

  return (
    <div className="flex min-h-32 min-w-0 flex-col gap-3 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {t("imports.successTitle", { account: summary.account_name })}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("imports.success", {
              inserted: summary.inserted,
              duplicates: summary.duplicates,
              skipped: summary.skipped_rows,
            })}
          </p>
          {missingFxCount > 0 ? (
            <p className="mt-1 text-xs font-medium text-muted-foreground">
              {t("imports.successMissingFx", { count: missingFxCount })}
            </p>
          ) : null}
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        className="shrink-0 self-end sm:self-auto"
        asChild
      >
        <Link href={transactionsHref({ import_id: summary.import_id })}>
          {t("imports.showTransactions")}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </Button>
    </div>
  );
}
