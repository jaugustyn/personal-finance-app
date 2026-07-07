export function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="min-h-[104px] rounded-md border bg-muted/20 p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 break-words text-lg font-semibold tabular-nums">
        {value}
      </div>
      {hint ? (
        <div className="mt-1 truncate text-xs text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}
