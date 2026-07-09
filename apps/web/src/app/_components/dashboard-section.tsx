"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function ChartCard({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base text-foreground">{title}</CardTitle>
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
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold tracking-normal text-foreground">
            {title}
          </h2>
          {description ? (
            <p className="max-w-2xl text-sm text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}
