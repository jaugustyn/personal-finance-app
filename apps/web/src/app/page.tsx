"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  PiggyBank,
  Wallet,
} from "lucide-react";
import { api } from "@/lib/api";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Money } from "@/components/money";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

export default function DashboardPage() {
  const { t } = useT();
  const months = 12;
  const [range, setRange] = useState<"12m" | "all">("12m");
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
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
          {recent.isLoading ? (
            <ChartSkeleton />
          ) : recent.data && recent.data.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("transactions.column.date")}</TableHead>
                  <TableHead>{t("transactions.column.merchant")}</TableHead>
                  <TableHead>{t("transactions.column.category")}</TableHead>
                  <TableHead className="text-right">
                    {t("transactions.column.amount")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recent.data.map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell className="text-muted-foreground">
                      {formatDate(tx.booking_date)}
                    </TableCell>
                    <TableCell className="font-medium">
                      {tx.merchant || tx.title}
                    </TableCell>
                    <TableCell>
                      {tx.category ? (
                        <Badge variant="secondary">
                          {tCategory(t, tx.category)}
                        </Badge>
                      ) : tx.category_predicted ? (
                        <Badge variant="outline">
                          {tCategory(t, tx.category_predicted)}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Money
                        amount={Number(tx.amount)}
                        currency={tx.currency}
                        direction={tx.direction}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState title={t("common.empty")} />
          )}
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
