"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import {
  LIMIT_OPTIONS,
  RANGE_OPTIONS,
  type DashboardLimit,
  type DashboardRange,
} from "../_lib/dashboard-types";

export function DashboardToolbar({
  range,
  includeTransfers,
  chartLimit,
  onRangeChange,
  onIncludeTransfersChange,
  onChartLimitChange,
}: {
  range: DashboardRange;
  includeTransfers: boolean;
  chartLimit: DashboardLimit;
  onRangeChange: (value: DashboardRange) => void;
  onIncludeTransfersChange: (value: boolean) => void;
  onChartLimitChange: (value: DashboardLimit) => void;
}) {
  const { t } = useT();
  const rangeLabels: Record<DashboardRange, string> = {
    "1m": t("dashboard.range.1m"),
    "3m": t("dashboard.range.3m"),
    "6m": t("dashboard.range.6m"),
    "12m": t("dashboard.range.12m"),
    all: t("dashboard.range.all"),
  };

  return (
    <section className="sticky -top-4 z-40 -mx-4 border-b bg-background px-4 py-3 sm:-top-6 sm:-mx-6 sm:px-6">
      <div className="flex flex-wrap items-end gap-3">
        <ToolbarGroup label={t("dashboard.toolbar.period")}>
          {RANGE_OPTIONS.map((value) => (
            <ToolbarButton
              key={value}
              active={range === value}
              onClick={() => onRangeChange(value)}
            >
              {rangeLabels[value]}
            </ToolbarButton>
          ))}
        </ToolbarGroup>
        <ToolbarGroup label={t("dashboard.toolbar.transfers")}>
          <ToolbarButton
            active={!includeTransfers}
            onClick={() => onIncludeTransfersChange(false)}
          >
            {t("dashboard.transfers.omitted")}
          </ToolbarButton>
          <ToolbarButton
            active={includeTransfers}
            onClick={() => onIncludeTransfersChange(true)}
          >
            {t("dashboard.transfers.included")}
          </ToolbarButton>
        </ToolbarGroup>
        <ToolbarGroup label={t("dashboard.toolbar.top")}>
          {LIMIT_OPTIONS.map((value) => (
            <ToolbarButton
              key={value}
              active={chartLimit === value}
              onClick={() => onChartLimitChange(value)}
            >
              {value}
            </ToolbarButton>
          ))}
        </ToolbarGroup>
      </div>
    </section>
  );
}

export function ToolbarGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <div className="flex h-4 items-center px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 inline-flex min-h-10 max-w-full flex-wrap items-center gap-1 rounded-lg border bg-muted/40 p-1 shadow-inner shadow-foreground/[0.03]">
        {children}
      </div>
    </div>
  );
}

export function ToolbarButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-8 items-center whitespace-nowrap rounded-md px-3.5 text-xs font-medium leading-none transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
        active
          ? "bg-card text-foreground shadow-sm ring-1 ring-border/80"
          : "text-muted-foreground hover:bg-background/70 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
