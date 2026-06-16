import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function FilterPanel({
  children,
  actions,
  hint,
  className,
  gridClassName,
}: {
  children: ReactNode;
  actions?: ReactNode;
  hint?: ReactNode;
  className?: string;
  gridClassName?: string;
}) {
  return (
    <Card className={className}>
      <CardContent className="pt-6">
        <div
          className={cn(
            "grid gap-3 md:grid-cols-2 xl:grid-cols-6",
            gridClassName,
          )}
        >
          {children}
        </div>
        {hint ? (
          <div className="mt-3 text-xs text-muted-foreground">{hint}</div>
        ) : null}
        {actions ? (
          <div className="mt-4 flex flex-wrap items-center gap-3 border-t pt-4">
            {actions}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function FilterField({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label className="text-xs font-medium text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}
