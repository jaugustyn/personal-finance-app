"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { KpiCard } from "@/components/kpi-card";
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
  CategoryDonut,
  NetWorthChart,
  TopMerchantsBar,
} from "@/components/charts";
import { formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import { useT, tCategory } from "@/lib/i18n";

export default function DashboardPage() {
  const { t } = useT();
  const months = 12;
  const overview = useQuery({
    queryKey: ["overview", months],
    queryFn: () => api.overview(months),
  });
  const cashflow = useQuery({
    queryKey: ["cashflow"],
    queryFn: () => api.cashflow(12),
  });
  const byCategory = useQuery({
    queryKey: ["byCategory"],
    queryFn: () => api.byCategory(3),
  });
  const networth = useQuery({
    queryKey: ["networth"],
    queryFn: () => api.networth(24),
  });
  const topMerchants = useQuery({
    queryKey: ["topMerchants"],
    queryFn: () => api.topMerchants(3, 8),
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
  const monthlyAvg = o && months > 0 ? netCashflow / months : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("nav.dashboard")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.subtitle")}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={t("dashboard.kpi.income")}
          value={o ? formatCurrency(totalIncome) : "—"}
          hint={o ? t("dashboard.kpi.txCount", { n: o.tx_count }) : undefined}
          trend="up"
        />
        <KpiCard
          label={t("dashboard.kpi.expenses")}
          value={o ? formatCurrency(totalExpenses) : "—"}
          trend="down"
        />
        <KpiCard
          label={t("dashboard.kpi.net")}
          value={o ? formatCurrency(netCashflow) : "—"}
          hint={savingsHint}
          trend={o && netCashflow >= 0 ? "up" : "down"}
        />
        <KpiCard
          label={t("dashboard.kpi.monthlyAvg")}
          value={monthlyAvg != null ? formatCurrency(monthlyAvg) : "—"}
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
              {t("dashboard.byCategoryTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {byCategory.isLoading ? (
              <ChartSkeleton />
            ) : byCategory.data && byCategory.data.length > 0 ? (
              <CategoryDonut data={byCategory.data} />
            ) : (
              <Empty />
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
              {t("dashboard.topMerchantsTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topMerchants.isLoading ? (
              <ChartSkeleton />
            ) : topMerchants.data && topMerchants.data.length > 0 ? (
              <TopMerchantsBar data={topMerchants.data} />
            ) : (
              <Empty />
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
                    <TableCell
                      className={`text-right tabular-nums ${tx.direction === "debit" ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}
                    >
                      {tx.direction === "debit" ? "-" : "+"}
                      {formatCurrency(Math.abs(Number(tx.amount)), tx.currency)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty />
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

function Empty() {
  const { t } = useT();
  return (
    <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
      {t("common.empty")}
    </div>
  );
}
