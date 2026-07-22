"use client";

import * as React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
  variant?: "default" | "compact";
}

export function ErrorState({
  title,
  description,
  onRetry,
  className,
  variant = "default",
}: ErrorStateProps) {
  const { t } = useT();
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-destructive/30 bg-destructive/5 text-center",
        variant === "compact" ? "gap-2 p-4" : "gap-3 p-8",
        className,
      )}
    >
      <div
        className={cn(
          "flex items-center justify-center rounded-full bg-destructive/12 text-destructive",
          variant === "compact" ? "h-8 w-8" : "h-11 w-11",
        )}
      >
        <AlertTriangle className={variant === "compact" ? "h-4 w-4" : "h-5 w-5"} />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium">{title ?? t("common.error")}</p>
        {description && (
          <p className="max-w-sm text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}
