import type { MlModelComparison } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { estimatorName, percent } from "../_lib/ml-format";

export function ModelComparisonCard({ rows }: { rows: MlModelComparison[] }) {
  const { t } = useT();
  const { formatPercent } = useFormatters();
  const recommended = rows.find((row) => row.is_recommended);
  if (rows.length === 0) return null;

  const columns: DataTableColumn<MlModelComparison>[] = [
    {
      id: "model",
      header: t("ml.comparison.model"),
      sortValue: (row) => row.rank ?? 999,
      className: "font-medium",
      cell: (row) => (
        <>
          <span className="mr-2 text-xs text-muted-foreground">#{row.rank}</span>
          {estimatorName(row.estimator)}
        </>
      ),
    },
    {
      id: "stability",
      header: t("ml.comparison.weakestMacro"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.stability_score,
      cell: (row) => percent(row.stability_score, formatPercent),
    },
    {
      id: "macro",
      header: t("ml.comparison.meanMacro"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.macro_f1,
      cell: (row) => percent(row.macro_f1, formatPercent),
    },
    {
      id: "coverage",
      header: t("ml.comparison.coverage"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.coverage_at_055,
      cell: (row) => percent(row.coverage_at_055, formatPercent),
    },
    {
      id: "accuracy",
      header: t("ml.comparison.accuracy"),
      align: "right",
      className: "tabular-nums",
      sortValue: (row) => row.accuracy_at_055,
      cell: (row) => percent(row.accuracy_at_055, formatPercent),
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
            <Badge variant="warning">
              {t("ml.comparison.requirementsFailed")}
            </Badge>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <section className="space-y-3">
      <div className="flex min-h-9 items-center">
        <h2 className="text-base font-semibold text-foreground">
          {t("ml.comparison.rankingTitle")}
        </h2>
      </div>
      <DataTable
        columns={columns}
        data={rows}
        rowKey={(row) => row.model_id}
        initialSort={{ id: "model", dir: "asc" }}
        tableClassName="min-w-[720px]"
        getRowClassName={(row) =>
          row.is_recommended ? "bg-primary/5" : undefined
        }
      />
      <p className="text-xs text-muted-foreground">
        {recommended
          ? t("ml.comparison.recommendationExplanation")
          : t("ml.comparison.noRecommendationExplanation")}
      </p>
    </section>
  );
}
