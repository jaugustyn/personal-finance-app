"use client";

import type { ComponentType } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  PiggyBank,
  Percent,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { useT } from "@/lib/i18n";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

export function FinancialSnapshot({
  income,
  expenses,
  net,
  savingsRate,
  currency,
  isLoading,
}: {
  income: number;
  expenses: number;
  net: number;
  savingsRate: number;
  currency: string;
  isLoading: boolean;
}) {
  const { t } = useT();

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <SnapshotCard
        label={t("dashboard.kpi.income")}
        value={isLoading ? "..." : formatCurrency(income, currency)}
        icon={ArrowUpCircle}
        tone="positive"
      />
      <SnapshotCard
        label={t("dashboard.kpi.expenses")}
        value={isLoading ? "..." : formatCurrency(expenses, currency)}
        icon={ArrowDownCircle}
        tone="negative"
      />
      <SnapshotCard
        label={t("dashboard.kpi.net")}
        value={isLoading ? "..." : formatCurrency(net, currency)}
        icon={PiggyBank}
        tone="pink"
      />
      <SnapshotCard
        label={t("dashboard.kpi.savings")}
        value={isLoading ? "..." : formatPercent(savingsRate)}
        icon={Percent}
        tone={savingsRateTone(savingsRate)}
      />
    </section>
  );
}

function SnapshotCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
  tone: SnapshotTone;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium text-muted-foreground">{label}</div>
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-md border",
              tone === "positive" &&
                "border-positive/20 bg-positive/10 text-positive",
              tone === "negative" &&
                "border-negative/20 bg-negative/10 text-negative",
              tone === "info" && "border-info/20 bg-info/10 text-info",
              tone === "warning" &&
                "border-warning/20 bg-warning/10 text-warning",
              tone === "pink" && "border-chart-6/20 bg-chart-6/10 text-chart-6",
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-3 text-xl font-semibold tracking-tight text-foreground md:text-2xl">
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

type SnapshotTone = "positive" | "negative" | "info" | "warning" | "pink";

function savingsRateTone(value: number): SnapshotTone {
  if (value < 0) return "negative";
  if (value < 0.1) return "warning";
  if (value < 0.3) return "info";
  return "positive";
}
