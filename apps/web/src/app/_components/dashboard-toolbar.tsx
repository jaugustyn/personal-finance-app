"use client";

import type { ReactNode } from "react";

import { Switch } from "@/components/ui/switch";
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
    <section className="sticky -top-4 z-40 -mx-4 border-b border-border/70 bg-background/95 px-4 py-4 backdrop-blur sm:-top-6 sm:-mx-6 sm:px-6">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
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
        <ToolbarGroup label={t("dashboard.toolbar.limit")}>
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
        <div className="min-w-0">
          <div className="mb-1 flex h-4 items-center px-0.5 text-xs font-medium text-muted-foreground">
            {t("dashboard.transfers.include")}
          </div>
          <div className="flex h-9 items-center px-1">
            <Switch
              checked={includeTransfers}
              onCheckedChange={onIncludeTransfersChange}
              aria-label={t("dashboard.transfers.include")}
            />
          </div>
        </div>
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
      <div className="mb-1 flex h-4 items-center px-0.5 text-xs font-medium text-muted-foreground">
        {label}
      </div>
      <div className="inline-flex h-9 max-w-full items-stretch divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card">
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
        "relative flex h-full items-center whitespace-nowrap px-3 text-xs font-medium leading-none transition-colors focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        active
          ? "bg-accent-soft text-accent-soft-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
