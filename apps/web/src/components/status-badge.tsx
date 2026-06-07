import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Severity = "low" | "medium" | "high" | "critical";

const severityVariant: Record<
  Severity,
  React.ComponentProps<typeof Badge>["variant"]
> = {
  low: "muted",
  medium: "info",
  high: "warning",
  critical: "destructive",
};

export function SeverityBadge({
  severity,
  children,
  className,
}: {
  severity: Severity;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Badge variant={severityVariant[severity]} className={className}>
      {children}
    </Badge>
  );
}

/** Confidence in [0,1] → colored badge with a low/medium/high bucket. */
export function ConfidenceBadge({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  const variant =
    value >= 0.75 ? "success" : value >= 0.5 ? "warning" : "muted";
  return (
    <Badge
      variant={variant as React.ComponentProps<typeof Badge>["variant"]}
      className={cn("tabular-nums", className)}
    >
      {Math.round(value * 100)}%
    </Badge>
  );
}
