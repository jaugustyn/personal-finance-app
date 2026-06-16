export const PIE_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "hsl(220 70% 65%)",
  "hsl(160 60% 60%)",
  "hsl(30 80% 70%)",
  "hsl(245 75% 68%)",
];

export function tooltipStyle() {
  return {
    backgroundColor: "hsl(var(--popover))",
    border: "1px solid hsl(var(--border))",
    borderRadius: 8,
    color: "hsl(var(--popover-foreground))",
    fontSize: 12,
  };
}

export function truncateChartLabel(value: unknown, maxLength = 18): string {
  const text = String(value ?? "");
  if (text.length <= maxLength) return text;
  if (maxLength <= 3) return text.slice(0, maxLength);
  return `${text.slice(0, maxLength - 3).trimEnd()}...`;
}

export function formatCompactAxisNumber(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  if (Math.abs(number) >= 1000) return `${Math.round(number / 1000)}k`;
  return String(Math.round(number));
}

export interface SankeyNodeProps {
  x: number;
  y: number;
  width: number;
  height: number;
  index: number;
  payload?: { name?: string };
}
