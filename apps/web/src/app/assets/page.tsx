"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Asset, type AssetInput } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { KpiCard } from "@/components/kpi-card";
import { PortfolioHistoryChart, SankeyFlow } from "@/components/charts";
import { formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { Loader2, RefreshCw, Trash2, Plus } from "lucide-react";
import { useT } from "@/lib/i18n";

export default function AssetsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const assets = useQuery({
    queryKey: ["assets"],
    queryFn: () => api.assets(),
  });
  const summary = useQuery({
    queryKey: ["portfolioSummary"],
    queryFn: () => api.portfolioSummary(),
  });
  const history = useQuery({
    queryKey: ["assetHistory"],
    queryFn: () => api.assetHistory(180),
  });
  const sankey = useQuery({
    queryKey: ["sankey", 3],
    queryFn: () => api.sankey(3, 8, 4),
  });

  const refresh = useMutation({
    mutationFn: () => api.refreshAssets(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["portfolioSummary"] });
      qc.invalidateQueries({ queryKey: ["assetHistory"] });
    },
  });

  const create = useMutation({
    mutationFn: (payload: AssetInput) => api.createAsset(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["portfolioSummary"] });
      setForm({
        symbol: "",
        name: "",
        asset_class: "equity",
        currency: "USD",
        quantity: "0",
        cost_basis: "0",
      });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["portfolioSummary"] });
    },
  });

  const [form, setForm] = useState({
    symbol: "",
    name: "",
    asset_class: "equity",
    currency: "USD",
    quantity: "0",
    cost_basis: "0",
  });

  const s = summary.data;
  const totalValue = s ? Number(s.total_value_pln) : 0;
  const totalCost = s ? Number(s.total_cost_pln) : 0;
  const pnl = s ? Number(s.pnl_pln) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("assets.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("assets.subtitle")}
          </p>
        </div>
        <Button onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          {refresh.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          {t("assets.refresh")}
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={t("assets.kpi.value")}
          value={s ? formatCurrency(totalValue) : "—"}
          hint={
            s?.last_refresh
              ? t("assets.kpi.lastRefresh", {
                  date: formatDate(s.last_refresh),
                })
              : undefined
          }
        />
        <KpiCard
          label={t("assets.kpi.cost")}
          value={s ? formatCurrency(totalCost) : "—"}
        />
        <KpiCard
          label={t("assets.kpi.pnl")}
          value={s ? formatCurrency(pnl) : "—"}
          trend={pnl >= 0 ? "up" : "down"}
          hint={s ? formatPercent(s.pnl_pct) : undefined}
        />
        <KpiCard
          label={t("assets.kpi.count")}
          value={s ? String(s.asset_count) : "—"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("assets.historyTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {history.isLoading ? (
              <ChartSkeleton />
            ) : history.data && history.data.length > 0 ? (
              <PortfolioHistoryChart data={history.data} />
            ) : (
              <div className="flex h-60 items-center justify-center text-sm text-muted-foreground">
                {t("assets.historyEmpty")}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">
              {t("assets.add")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (!form.symbol.trim()) return;
                create.mutate({
                  symbol: form.symbol.trim().toUpperCase(),
                  name: form.name,
                  asset_class: form.asset_class,
                  currency: form.currency.toUpperCase(),
                  quantity: Number(form.quantity) || 0,
                  cost_basis: Number(form.cost_basis) || 0,
                });
              }}
            >
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">
                  {t("assets.field.symbol")}
                </label>
                <Input
                  value={form.symbol}
                  onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                  placeholder="AAPL"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">
                  {t("assets.field.name")}
                </label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Apple Inc."
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.class")}
                  </label>
                  <select
                    value={form.asset_class}
                    onChange={(e) =>
                      setForm({ ...form, asset_class: e.target.value })
                    }
                    className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  >
                    <option value="equity">{t("assets.class.equity")}</option>
                    <option value="etf">{t("assets.class.etf")}</option>
                    <option value="crypto">{t("assets.class.crypto")}</option>
                    <option value="bond">{t("assets.class.bond")}</option>
                    <option value="cash">{t("assets.class.cash")}</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.currency")}
                  </label>
                  <Input
                    value={form.currency}
                    onChange={(e) =>
                      setForm({ ...form, currency: e.target.value })
                    }
                    maxLength={3}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.quantity")}
                  </label>
                  <Input
                    type="number"
                    step="0.00000001"
                    value={form.quantity}
                    onChange={(e) =>
                      setForm({ ...form, quantity: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.cost")}
                  </label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.cost_basis}
                    onChange={(e) =>
                      setForm({ ...form, cost_basis: e.target.value })
                    }
                  />
                </div>
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={create.isPending}
              >
                {create.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                {t("common.add")}
              </Button>
              {create.isError && (
                <p className="text-xs text-destructive">
                  {(create.error as Error).message}
                </p>
              )}
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("assets.positions")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {assets.isLoading ? (
            <div className="flex h-40 items-center justify-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : !assets.data || assets.data.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
              {t("assets.empty")}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("assets.column.symbol")}</TableHead>
                  <TableHead>{t("assets.column.class")}</TableHead>
                  <TableHead className="text-right">
                    {t("assets.column.quantity")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("assets.column.price")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("assets.column.value")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("assets.column.pnl")}
                  </TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {assets.data.map((a: Asset) => {
                  const value =
                    a.last_value_pln != null ? Number(a.last_value_pln) : null;
                  const apnl = a.pnl_pln != null ? Number(a.pnl_pln) : null;
                  return (
                    <TableRow key={a.id}>
                      <TableCell>
                        <div className="font-medium">{a.symbol}</div>
                        <div className="text-xs text-muted-foreground">
                          {a.name || "—"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{a.asset_class}</Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {Number(a.quantity)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {a.last_price != null
                          ? `${Number(a.last_price).toFixed(2)} ${a.currency}`
                          : "—"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {value != null ? formatCurrency(value) : "—"}
                      </TableCell>
                      <TableCell
                        className={`text-right tabular-nums ${apnl != null ? (apnl >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400") : ""}`}
                      >
                        {apnl != null ? formatCurrency(apnl) : "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => {
                            if (
                              confirm(
                                t("assets.deleteConfirm", { symbol: a.symbol }),
                              )
                            )
                              remove.mutate(a.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("assets.sankeyTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {sankey.isLoading ? (
            <ChartSkeleton />
          ) : sankey.data ? (
            <SankeyFlow data={sankey.data} />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="flex h-60 items-center justify-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
    </div>
  );
}
