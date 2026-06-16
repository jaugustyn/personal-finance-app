"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  PiggyBank,
  Wallet,
} from "lucide-react";
import { api, type Transaction } from "@/lib/api";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Money } from "@/components/money";
import { EmptyState } from "@/components/empty-state";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CashflowChart,
  CategoryMoMChart,
  CategoryTrendChart,
  FrequentMerchantsBar,
  NetWorthChart,
  TopMerchantsBar,
} from "@/components/charts";
import { cn, formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import { useT, tCategory } from "@/lib/i18n";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { transactionsHref } from "@/lib/transaction-links";

export default function DashboardPage() {
  const { t } = useT();
  const months = 12;
  const [range, setRange] = useLocalStorageState<"12m" | "all">(
    "finance.dashboard.range",
    "12m",
  );
  const allData = range === "all";
  const overview = useQuery({
    queryKey: ["overview", months, range],
    queryFn: () => api.overview(months, allData),
  });
  const cashflow = useQuery({
    queryKey: ["cashflow", months, range],
    queryFn: () => api.cashflow(months, allData),
  });
  const categoryTrend = useQuery({
    queryKey: ["categoryTrend", months, range],
    queryFn: () => api.categoryTrend(months, 5, allData),
  });
  const networth = useQuery({
    queryKey: ["networth", months, range],
    queryFn: () => api.networth(months, allData),
  });
  const topMerchants = useQuery({
    queryKey: ["topMerchants", months, range],
    queryFn: () => api.topMerchants(months, 10, "amount", allData),
  });
  const frequentMerchants = useQuery({
    queryKey: ["frequentMerchants", months, range],
    queryFn: () => api.topMerchants(months, 10, "count", allData),
  });
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () => api.transactions({ limit: 6 }),
  });

  const o = overview.data;
  const totalIncome = o ? Number(o.total_income) : 0;
  const totalExpenses = o ? Number(o.total_expenses) : 0;
  const netCashflow = o ? Number(o.net_cashflow) : 0;
  const savingsHint = o
    ? t("dashboard.kpi.savingsHint", {
        value: formatPercent(Number(o.savings_rate)),
      })
    : undefined;
  const averageMonths = allData
    ? Math.max(cashflow.data?.length ?? 0, 1)
    : months;
  const monthlyAvg = o && averageMonths > 0 ? netCashflow / averageMonths : null;

  const sparklines = useMemo(() => {
    const data = cashflow.data ?? [];
    return {
      income: data.map((d) => Number(d.income)),
      expenses: data.map((d) => Number(d.expenses)),
      net: data.map((d) => Number(d.net)),
    };
  }, [cashflow.data]);
  const recentColumns: DataTableColumn<Transaction>[] = [
    {
      id: "date",
      header: t("transactions.column.date"),
      sortValue: (tx) => tx.booking_date,
      className: "text-muted-foreground",
      cell: (tx) => formatDate(tx.booking_date),
    },
    {
      id: "merchant",
      header: t("transactions.column.merchant"),
      sortValue: (tx) => tx.merchant || tx.title,
      className: "font-medium",
      cell: (tx) => (
        <Link
          href={transactionsHref({ search: tx.merchant || tx.title })}
          className="text-primary underline-offset-4 hover:underline"
        >
          {tx.merchant || tx.title}
        </Link>
      ),
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (tx) => tx.category ?? tx.category_predicted ?? "",
      cell: (tx) =>
        tx.category ? (
          <Badge variant="secondary">{tCategory(t, tx.category)}</Badge>
        ) : tx.category_predicted ? (
          <Badge variant="outline">{tCategory(t, tx.category_predicted)}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "amount",
      header: t("transactions.column.amount"),
      align: "right",
      sortValue: (tx) => Number(tx.amount),
      cell: (tx) => (
        <Money
          amount={Number(tx.amount)}
          currency={tx.currency}
          direction={tx.direction}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.dashboard")}
        description={t("dashboard.subtitle")}
      />

      <div className="inline-flex rounded-lg border border-border p-1">
        {(["12m", "all"] as const).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setRange(value)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              range === value
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(`dashboard.range.${value}`)}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={t("dashboard.kpi.income")}
          value={o ? formatCurrency(totalIncome) : "—"}
          hint={o ? t("dashboard.kpi.txCount", { n: o.tx_count }) : undefined}
          trend="up"
          icon={ArrowUpCircle}
          sparkline={sparklines.income}
        />
        <KpiCard
          label={t("dashboard.kpi.expenses")}
          value={o ? formatCurrency(totalExpenses) : "—"}
          trend="down"
          icon={ArrowDownCircle}
          sparkline={sparklines.expenses}
        />
        <KpiCard
          label={t("dashboard.kpi.net")}
          value={o ? formatCurrency(netCashflow) : "—"}
          hint={savingsHint}
          trend={o && netCashflow >= 0 ? "up" : "down"}
          icon={PiggyBank}
          sparkline={sparklines.net}
        />
        <KpiCard
          label={t("dashboard.kpi.monthlyAvg")}
          value={monthlyAvg != null ? formatCurrency(monthlyAvg) : "—"}
          icon={Wallet}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("dashboard.cashflowTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {cashflow.isLoading ? (
              <ChartSkeleton />
            ) : cashflow.data ? (
              <CashflowChart data={cashflow.data} />
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("dashboard.topMerchantsTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topMerchants.isLoading ? (
              <ChartSkeleton />
            ) : topMerchants.data && topMerchants.data.length > 0 ? (
              <TopMerchantsBar data={topMerchants.data} />
            ) : (
              <EmptyState title={t("common.empty")} />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("dashboard.categoryTrendTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {categoryTrend.isLoading ? (
              <ChartSkeleton />
            ) : categoryTrend.data && categoryTrend.data.length > 0 ? (
              <CategoryTrendChart data={categoryTrend.data} />
            ) : (
              <EmptyState title={t("common.empty")} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("dashboard.frequentTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {frequentMerchants.isLoading ? (
              <ChartSkeleton />
            ) : frequentMerchants.data && frequentMerchants.data.length > 0 ? (
              <FrequentMerchantsBar data={frequentMerchants.data} />
            ) : (
              <EmptyState title={t("common.empty")} />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("dashboard.networthTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {networth.isLoading ? (
              <ChartSkeleton />
            ) : networth.data ? (
              <NetWorthChart data={networth.data} />
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("dashboard.momTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {categoryTrend.isLoading ? (
              <ChartSkeleton />
            ) : categoryTrend.data && categoryTrend.data.length > 0 ? (
              <CategoryMoMChart data={categoryTrend.data} />
            ) : (
              <EmptyState title={t("common.empty")} />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("dashboard.recentTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={recentColumns}
            data={recent.data}
            rowKey={(tx) => tx.id}
            isLoading={recent.isLoading}
            emptyTitle={t("common.empty")}
            initialSort={{ id: "date", dir: "desc" }}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="flex h-72 items-center justify-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
    </div>
  );
}
