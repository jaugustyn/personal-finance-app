"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type Asset, type AssetInput } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/page-header";
import { Money } from "@/components/money";
import { useConfirm } from "@/components/confirm-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { KpiCard } from "@/components/kpi-card";
import { PortfolioHistoryChart } from "@/components/charts";
import { formatCurrency, formatDate, formatPercent } from "@/lib/utils";
import { Loader2, RefreshCw, Trash2, Plus } from "lucide-react";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";

/** Currencies offered when adding a position (kept simple, no live FX list). */
const CURRENCIES = [
  "PLN",
  "USD",
  "EUR",
  "GBP",
  "CHF",
  "JPY",
  "CAD",
  "AUD",
] as const;

export default function AssetsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
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

  const refresh = useMutation({
    mutationFn: () => api.refreshAssets(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["portfolioSummary"] });
      qc.invalidateQueries({ queryKey: ["assetHistory"] });
      toast.success(t("toast.refreshed"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
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
      toast.success(t("toast.saved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["portfolioSummary"] });
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
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
  const isCash = form.asset_class === "cash";
  const assetColumns: DataTableColumn<Asset>[] = [
    {
      id: "symbol",
      header: t("assets.column.symbol"),
      sortValue: (a) => `${a.symbol} ${a.name ?? ""}`,
      cell: (a) => (
        <div>
          <div className="font-medium">{a.symbol}</div>
          <div className="text-xs text-muted-foreground">{a.name || "—"}</div>
        </div>
      ),
    },
    {
      id: "asset_class",
      header: t("assets.column.class"),
      sortValue: (a) => a.asset_class,
      cell: (a) => <Badge variant="outline">{a.asset_class}</Badge>,
    },
    {
      id: "quantity",
      header: t("assets.column.quantity"),
      align: "right",
      className: "tabular-nums",
      sortValue: (a) => Number(a.quantity),
      cell: (a) => Number(a.quantity),
    },
    {
      id: "price",
      header: t("assets.column.price"),
      align: "right",
      className: "tabular-nums text-muted-foreground",
      sortValue: (a) => (a.last_price != null ? Number(a.last_price) : null),
      cell: (a) =>
        a.last_price != null
          ? `${Number(a.last_price).toFixed(2)} ${a.currency}`
          : "—",
    },
    {
      id: "value",
      header: t("assets.column.value"),
      align: "right",
      className: "tabular-nums",
      sortValue: (a) =>
        a.last_value_pln != null ? Number(a.last_value_pln) : null,
      cell: (a) =>
        a.last_value_pln != null
          ? formatCurrency(Number(a.last_value_pln))
          : "—",
    },
    {
      id: "pnl",
      header: t("assets.column.pnl"),
      align: "right",
      sortValue: (a) => (a.pnl_pln != null ? Number(a.pnl_pln) : null),
      cell: (a) =>
        a.pnl_pln != null ? <Money amount={Number(a.pnl_pln)} signed /> : "—",
    },
    {
      id: "actions",
      header: "",
      align: "right",
      headerClassName: "w-12",
      className: "w-12",
      cell: (a) => (
        <Button
          size="icon"
          variant="ghost"
          onClick={async () => {
            const ok = await confirm({
              title: t("assets.deleteConfirm", {
                symbol: a.symbol,
              }),
              destructive: true,
            });
            if (ok) remove.mutate(a.id);
          }}
          aria-label={t("common.delete")}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("assets.title")}
        description={t("assets.subtitle")}
        actions={
          <Button onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            {refresh.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            {t("assets.refresh")}
          </Button>
        }
      />

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
                if (isCash) {
                  const qty = Number(form.quantity) || 0;
                  if (qty <= 0) return;
                  const ccy = form.currency.toUpperCase();
                  create.mutate({
                    symbol: ccy,
                    name: t("assets.class.cash"),
                    asset_class: "cash",
                    currency: ccy,
                    quantity: qty,
                    cost_basis: qty,
                  });
                  return;
                }
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
              {!isCash && (
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.symbol")}
                  </label>
                  <Input
                    value={form.symbol}
                    onChange={(e) =>
                      setForm({ ...form, symbol: e.target.value })
                    }
                    placeholder="AAPL"
                  />
                </div>
              )}
              {!isCash && (
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
              )}
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.class")}
                  </label>
                  <Select
                    value={form.asset_class}
                    onValueChange={(v) => setForm({ ...form, asset_class: v })}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="equity">
                        {t("assets.class.equity")}
                      </SelectItem>
                      <SelectItem value="etf">
                        {t("assets.class.etf")}
                      </SelectItem>
                      <SelectItem value="crypto">
                        {t("assets.class.crypto")}
                      </SelectItem>
                      <SelectItem value="bond">
                        {t("assets.class.bond")}
                      </SelectItem>
                      <SelectItem value="cash">
                        {t("assets.class.cash")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {t("assets.field.currency")}
                  </label>
                  <Select
                    value={form.currency}
                    onValueChange={(v) => setForm({ ...form, currency: v })}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CURRENCIES.map((ccy) => (
                        <SelectItem key={ccy} value={ccy}>
                          {ccy}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    {isCash
                      ? t("assets.field.amount")
                      : t("assets.field.quantity")}
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
                {!isCash && (
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
                )}
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
          <DataTable
            columns={assetColumns}
            data={assets.data}
            rowKey={(a) => a.id}
            isLoading={assets.isLoading}
            emptyTitle={t("assets.empty")}
            initialSort={{ id: "value", dir: "desc" }}
          />
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
