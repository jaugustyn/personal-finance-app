"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Direction } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatDate } from "@/lib/utils";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useT, tCategory } from "@/lib/i18n";

function severityVariant(
  severity: number,
): "default" | "warning" | "destructive" {
  if (severity >= 0.75) return "destructive";
  if (severity >= 0.5) return "warning";
  return "default";
}

export default function AnomaliesPage() {
  const { t } = useT();
  const [direction, setDirection] = useState<Direction>("debit");
  const query = useQuery({
    queryKey: ["anomalies", direction],
    queryFn: () => api.anomalies({ direction }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("anomalies.title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("anomalies.subtitle")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("anomalies.filter")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as Direction)}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
          >
            <option value="debit">
              {t("transactions.filterDirection.debit")}
            </option>
            <option value="credit">
              {t("transactions.filterDirection.credit")}
            </option>
            <option value="all">{t("transactions.filterDirection.all")}</option>
          </select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">
            {t("anomalies.top")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <TableSkeleton />
          ) : !query.data || query.data.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
              {t("anomalies.empty")}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("transactions.column.date")}</TableHead>
                  <TableHead>{t("transactions.column.merchant")}</TableHead>
                  <TableHead>{t("transactions.column.category")}</TableHead>
                  <TableHead>{t("anomalies.severity")}</TableHead>
                  <TableHead className="text-right">
                    {t("transactions.column.amount")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="text-muted-foreground">
                      {formatDate(a.booking_date)}
                    </TableCell>
                    <TableCell className="font-medium">
                      <div>{a.merchant || a.title}</div>
                      {a.reasons.length > 0 ? (
                        <div className="mt-1 max-w-[28rem] text-xs font-normal text-muted-foreground">
                          {a.reasons.join(", ")}
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {a.category ? (
                        <Badge variant="secondary">
                          {tCategory(t, a.category)}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={severityVariant(a.severity)}>
                        {(a.severity * 100).toFixed(0)}%
                      </Badge>
                    </TableCell>
                    <TableCell
                      className={`text-right tabular-nums ${a.direction === "debit" ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}
                    >
                      {a.direction === "debit" ? "-" : "+"}
                      {formatCurrency(Math.abs(Number(a.amount)))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
