import { Sparkles } from "lucide-react";

import type { MlModelComparison } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { percent } from "../_lib/ml-format";

export function ModelComparisonCard({ rows }: { rows: MlModelComparison[] }) {
  const { t } = useT();
  const hasRows = rows.length > 0;
  const columns: DataTableColumn<MlModelComparison>[] = [
    {
      id: "model",
      header: t("ml.comparison.model"),
      sortValue: (row) => row.rank ?? 999,
      className: "font-medium",
      cell: (row) => (
        <>
          <span className="mr-2 text-xs text-muted-foreground">#{row.rank}</span>
          {row.estimator}
        </>
      ),
    },
    {
      id: "features",
      header: t("ml.comparison.features"),
      sortValue: (row) => row.feature_set,
      className: "text-muted-foreground",
      cell: (row) => row.feature_set,
    },
    {
      id: "macro",
      header: t("ml.comparison.macro"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.macro_f1,
      cell: (row) => percent(row.macro_f1),
    },
    {
      id: "weighted",
      header: t("ml.comparison.weighted"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.weighted_f1,
      cell: (row) => percent(row.weighted_f1),
    },
    {
      id: "stability",
      header: t("ml.comparison.stability"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.stability_score,
      cell: (row) => percent(row.stability_score),
    },
    {
      id: "coverage",
      header: t("ml.comparison.coverage"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.coverage_at_055,
      cell: (row) => percent(row.coverage_at_055),
    },
    {
      id: "accuracy",
      header: t("ml.comparison.accuracy"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.accuracy_at_055,
      cell: (row) => percent(row.accuracy_at_055),
    },
    {
      id: "status",
      header: t("ml.comparison.status"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1">
          {row.is_recommended ? (
            <Badge variant="success">{t("ml.comparison.recommended")}</Badge>
          ) : null}
          {row.is_current ? (
            <Badge variant="secondary">{t("ml.comparison.current")}</Badge>
          ) : null}
          {row.skipped ? (
            <Badge variant="warning">{t("ml.comparison.skipped")}</Badge>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <Sparkles className="h-4 w-4 text-primary" />
          {t("ml.comparison.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {hasRows ? (
          <DataTable
            columns={columns}
            data={rows}
            rowKey={(row) => `${row.feature_set}-${row.estimator}`}
            initialSort={{ id: "model", dir: "asc" }}
            tableClassName="min-w-[840px]"
            getRowClassName={(row) =>
              row.is_recommended ? "bg-primary/5" : undefined
            }
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("ml.comparison.noReport")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
