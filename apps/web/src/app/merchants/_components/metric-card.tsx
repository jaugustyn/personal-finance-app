import { Card, CardContent } from "@/components/ui/card";

export function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="h-14">
      <CardContent className="flex h-full flex-col justify-center px-3 py-2">
        <div className="truncate text-[11px] leading-4 text-muted-foreground">{label}</div>
        <div className="text-lg font-semibold leading-6 tabular-nums">{value}</div>
      </CardContent>
    </Card>
  );
}
