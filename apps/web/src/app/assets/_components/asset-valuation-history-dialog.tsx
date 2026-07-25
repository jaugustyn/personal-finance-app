"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Edit3, History, Trash2 } from "lucide-react";
import { api, type AssetType, type AssetValuation } from "@/lib/api";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useFormatters, useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import {
  ASSET_RATE_DECIMAL_PLACES,
  formatAssetDecimal,
} from "../_lib/asset-number-format";
import { compoundingKey } from "../_lib/asset-options";

export interface HistoryTarget {
  itemId: number;
  itemName: string;
  assetType: AssetType;
  currency: string;
  readOnly?: boolean;
}

export function AssetValuationHistoryDialog({
  target,
  open,
  onOpenChange,
  onEdit,
  onDelete,
}: {
  target: HistoryTarget | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: (target: HistoryTarget, valuation: AssetValuation) => void;
  onDelete: (valuation: AssetValuation) => void;
}) {
  const { t } = useT();
  const { formatCurrency, formatDate, localeTag } = useFormatters();
  const query = useQuery({
    queryKey: queryKeys.assets.valuations(target?.itemId ?? null),
    queryFn: () => api.assetValuations(target!.itemId),
    enabled: open && Boolean(target),
  });

  const columns = useMemo<DataTableColumn<AssetValuation>[]>(
    () => [
      {
        id: "date",
        header: t("assets.valuationDate"),
        sortValue: (row) => row.valuation_date,
        cell: (row) => formatDate(row.valuation_date),
      },
      {
        id: "value",
        header: t("assets.value"),
        sortValue: (row) => Number(row.total_value),
        cell: (row) => (
          <div className="space-y-0.5 text-right tabular-nums">
            <p className="font-medium">{formatCurrency(Number(row.total_value), row.currency)}</p>
            {row.amount_pln != null && row.currency !== "PLN" ? (
              <p className="text-xs text-muted-foreground">{formatCurrency(Number(row.amount_pln), "PLN")}</p>
            ) : null}
          </div>
        ),
        align: "right",
      },
      {
        id: "method",
        header: t("assets.valueChange"),
        sortValue: (row) => row.growth_mode,
        cell: (row) =>
          row.growth_mode === "fixed_rate" ? (
            <div className="text-sm">
              <p>
                {t("assets.growth.fixedRate")} ·{" "}
                {formatAssetDecimal(
                  row.annual_rate_percent ?? 0,
                  localeTag,
                  ASSET_RATE_DECIMAL_PLACES,
                )}
                %
              </p>
              {row.compounding ? (
                <p className="text-xs text-muted-foreground">{t(compoundingKey(row.compounding))}</p>
              ) : null}
            </div>
          ) : (
            <span className="text-muted-foreground">{t("assets.growth.none")}</span>
          ),
      },
      {
        id: "actions",
        header: "",
        align: "center",
        cell: (row) => (
          <div className="flex justify-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => target && onEdit(target, row)}
              aria-label={t("common.edit")}
            >
              <Edit3 className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-destructive hover:text-destructive"
              onClick={() => onDelete(row)}
              aria-label={t("common.delete")}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ),
        className: target?.readOnly ? "hidden" : undefined,
        headerClassName: target?.readOnly ? "hidden" : "w-24",
      },
    ],
    [formatCurrency, formatDate, localeTag, onDelete, onEdit, t, target],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("assets.valuationHistory")}</DialogTitle>
          <DialogDescription>{target?.itemName}</DialogDescription>
        </DialogHeader>
        <div className="pt-2">
          {query.isLoading ? <TableSkeleton rows={4} /> : null}
          {query.isError ? (
            <ErrorState title={t("assets.historyError")} onRetry={() => void query.refetch()} />
          ) : null}
          {query.data && query.data.length === 0 ? (
            <EmptyState icon={History} title={t("assets.noValuations")} />
          ) : null}
          {query.data && query.data.length > 0 ? (
            <DataTable
              columns={columns}
              data={query.data}
              rowKey={(row) => row.id}
              initialSort={{ id: "date", dir: "desc" }}
              pagination={{ mode: "client" }}
            />
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
