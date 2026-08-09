"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { HelpTooltip } from "@/components/help-tooltip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function ChartCard({
  title,
  hint,
  children,
  className,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        {hint ? (
          <HelpTooltip content={hint}>
            <CardTitle className="w-fit text-base text-foreground">
              {title}
            </CardTitle>
          </HelpTooltip>
        ) : (
          <CardTitle className="text-base text-foreground">{title}</CardTitle>
        )}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function ChartSkeleton() {
  return (
    <div className="flex h-72 items-center justify-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
    </div>
  );
}

export function DashboardSection({
  title,
  description,
  children,
  className,
  separated = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  separated?: boolean;
}) {
  return (
    <section className={cn("space-y-4", className)}>
      <div className={cn("mb-4", separated && "border-t pt-5")}>
        <div>
          {description ? (
            <HelpTooltip content={description}>
              <h2 className="w-fit text-lg font-semibold tracking-normal text-foreground">
                {title}
              </h2>
            </HelpTooltip>
          ) : (
            <h2 className="text-lg font-semibold tracking-normal text-foreground">
              {title}
            </h2>
          )}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}
