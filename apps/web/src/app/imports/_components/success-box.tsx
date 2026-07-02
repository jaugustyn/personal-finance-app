"use client";

import { CheckCircle2 } from "lucide-react";

import type { ImportSummary } from "@/lib/api";
import { useT } from "@/lib/i18n";

export function SuccessBox({ summary }: { summary: ImportSummary }) {
  const { t } = useT();
  return (
    <div className="flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">
      <CheckCircle2 className="h-4 w-4" />
      {t("imports.success", {
        inserted: summary.inserted,
        duplicates: summary.duplicates,
      })}
    </div>
  );
}
