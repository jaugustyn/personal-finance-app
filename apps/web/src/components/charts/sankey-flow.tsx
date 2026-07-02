"use client";

import { ResponsiveContainer, Sankey, Tooltip } from "recharts";
import { useMemo } from "react";
import type { SankeyData } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { SankeyNodeProps, tooltipStyle } from "./chart-utils";

export function SankeyFlow({ data }: { data: SankeyData }) {
  const formatted = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n, name: n.name })),
      links: data.links.map((l) => ({
        source: l.source,
        target: l.target,
        value: Number(l.value),
      })),
    }),
    [data],
  );
  if (formatted.nodes.length === 0 || formatted.links.length === 0) {
    return (
      <div className="flex h-60 items-center justify-center text-sm text-muted-foreground">
        Brak danych do przepływu
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={420}>
      <Sankey
        data={formatted}
        nodePadding={24}
        nodeWidth={12}
        margin={{ top: 8, right: 100, bottom: 8, left: 80 }}
        link={{ stroke: "hsl(var(--chart-4))", strokeOpacity: 0.25 }}
        node={({ x, y, width, height, index, payload }: SankeyNodeProps) => (
          <g>
            <rect x={x} y={y} width={width} height={height} fill="hsl(var(--chart-4))" />
            <text
              x={x + (index === 0 ? -6 : width + 6)}
              y={y + height / 2}
              textAnchor={index === 0 ? "end" : "start"}
              dominantBaseline="middle"
              fontSize={11}
              fill="hsl(var(--foreground))"
            >
              {payload?.name}
            </text>
          </g>
        )}
      >
        <Tooltip
          contentStyle={tooltipStyle()}
          formatter={(value) => formatCurrency(Number(value))}
        />
      </Sankey>
    </ResponsiveContainer>
  );
}
