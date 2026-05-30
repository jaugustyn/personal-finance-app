"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  hint?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function KpiCard({ label, value, hint, trend, className }: KpiCardProps) {
  const trendColor =
    trend === "up"
      ? "text-emerald-600 dark:text-emerald-400"
      : trend === "down"
      ? "text-red-600 dark:text-red-400"
      : "text-muted-foreground";
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tracking-tight">{value}</div>
        {hint && <div className={cn("mt-1 text-xs", trendColor)}>{hint}</div>}
      </CardContent>
    </Card>
  );
}
