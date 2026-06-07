"use client";

import * as React from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Trend = "up" | "down" | "neutral";

interface KpiCardProps {
  label: string;
  value: string;
  /** Optional secondary line shown as a colored delta chip. */
  hint?: string;
  /** Drives the colored delta chip + arrow icon. */
  trend?: Trend;
  /** Optional sparkline series (numbers). */
  sparkline?: number[];
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}

const trendStyles: Record<
  Trend,
  {
    soft: string;
    stroke: string;
    Icon: React.ComponentType<{ className?: string }>;
  }
> = {
  up: {
    soft: "bg-positive/12 text-positive",
    stroke: "hsl(var(--chart-positive))",
    Icon: ArrowUpRight,
  },
  down: {
    soft: "bg-negative/12 text-negative",
    stroke: "hsl(var(--chart-negative))",
    Icon: ArrowDownRight,
  },
  neutral: {
    soft: "bg-muted text-muted-foreground",
    stroke: "hsl(var(--muted-foreground))",
    Icon: Minus,
  },
};

export function KpiCard({
  label,
  value,
  hint,
  trend = "neutral",
  sparkline,
  icon: Icon,
  className,
}: KpiCardProps) {
  const style = trendStyles[trend];
  const chartId = React.useId().replace(/:/g, "");
  const sparkData = sparkline?.map((v, i) => ({ i, v }));

  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            {Icon && <Icon className="h-4 w-4" />}
            <span>{label}</span>
          </div>
          {hint && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium",
                style.soft,
              )}
            >
              <style.Icon className="h-3 w-3" />
              {hint}
            </span>
          )}
        </div>

        <div className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">
          {value}
        </div>

        {sparkData && sparkData.length > 1 && (
          <div className="mt-3 h-10">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={sparkData}
                margin={{ top: 2, right: 0, bottom: 0, left: 0 }}
              >
                <defs>
                  <linearGradient
                    id={`spark-${chartId}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor={style.stroke}
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="100%"
                      stopColor={style.stroke}
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke={style.stroke}
                  strokeWidth={2}
                  fill={`url(#spark-${chartId})`}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
