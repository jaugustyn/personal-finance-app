"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CategoryCombobox } from "@/components/category-combobox";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type MerchantGroup } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency } from "@/lib/utils";

export function GroupsView() {
  const { t } = useT();
  const qc = useQueryClient();
  const [onlyUncat, setOnlyUncat] = useState(true);
  const [pickers, setPickers] = useState<Record<string, string | null>>({});

  const query = useQuery<MerchantGroup[]>({
    queryKey: ["transactions", "groups", { onlyUncat }],
    queryFn: () =>
      api.merchantGroups({ only_uncategorized: onlyUncat, min_count: 2 }),
  });

  const apply = useMutation({
    mutationFn: (vars: { merchant: string; category: string | null }) =>
      api.bulkCategorize({ merchant: vars.merchant, category: vars.category }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      setPickers((p) => {
        const next = { ...p };
        delete next[vars.merchant];
        return next;
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {t("transactions.groups.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t("transactions.groups.help")}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyUncat}
            onChange={(e) => setOnlyUncat(e.target.checked)}
            className="h-4 w-4"
          />
          {t("transactions.groups.onlyUncategorized")}
        </label>

        {query.isLoading ? (
          <TableSkeleton rows={6} />
        ) : (query.data ?? []).length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {t("transactions.groups.empty")}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("transactions.column.merchant")}</TableHead>
                <TableHead className="text-right">
                  {t("transactions.column.amount")}
                </TableHead>
                <TableHead className="text-center">#</TableHead>
                <TableHead>{t("transactions.column.category")}</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(query.data ?? []).map((g) => {
                const debit = Number(g.total_debit) || 0;
                const credit = Number(g.total_credit) || 0;
                const net = credit - debit;
                const picked =
                  g.merchant in pickers
                    ? pickers[g.merchant]
                    : (g.common_category ?? null);
                return (
                  <TableRow key={g.merchant}>
                    <TableCell className="font-medium">
                      <div>{g.merchant}</div>
                      {g.sample_titles.length > 0 && (
                        <div className="line-clamp-1 text-xs text-muted-foreground">
                          {g.sample_titles.slice(0, 2).join(" · ")}
                        </div>
                      )}
                    </TableCell>
                    <TableCell
                      className={`text-right tabular-nums ${
                        net < 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-emerald-600 dark:text-emerald-400"
                      }`}
                    >
                      {formatCurrency(net, "PLN")}
                    </TableCell>
                    <TableCell className="text-center text-muted-foreground">
                      {g.count}
                    </TableCell>
                    <TableCell>
                      <CategoryCombobox
                        value={picked}
                        onChange={(v) =>
                          setPickers((p) => ({ ...p, [g.merchant]: v }))
                        }
                        size="md"
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        disabled={apply.isPending || !picked}
                        onClick={() =>
                          apply.mutate({
                            merchant: g.merchant,
                            category: picked,
                          })
                        }
                      >
                        {t("transactions.groups.apply")}
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
  );
}
