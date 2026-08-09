import { tCategory, useFormatters, useT } from "@/lib/i18n";

export interface ClassCoverageValue {
  category: string;
  count?: number;
}

export function ClassCoverageGrid({
  title,
  values,
}: {
  title: string;
  values: ClassCoverageValue[];
}) {
  const { t } = useT();
  const { formatNumber } = useFormatters();

  return (
    <section>
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      {values.length ? (
        <div className="mt-2 grid gap-x-6 sm:grid-cols-2 xl:grid-cols-3">
          {values.map(({ category, count }) => {
            const name = tCategory(t, category);
            return (
              <div
                key={category}
                className="flex min-w-0 items-center justify-between gap-3 border-b py-1.5 text-sm"
              >
                <span className="truncate text-foreground" title={name}>
                  {name}
                </span>
                {count == null ? null : (
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {formatNumber(count)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <span className="mt-2 block text-xs text-muted-foreground">—</span>
      )}
    </section>
  );
}
