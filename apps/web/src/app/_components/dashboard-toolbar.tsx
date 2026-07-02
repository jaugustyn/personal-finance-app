"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function ToolbarGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-1">
      <div className="px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="inline-flex max-w-full flex-wrap rounded-lg border bg-background p-1">
        {children}
      </div>
    </div>
  );
}

export function ToolbarButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-8 rounded-md px-3 text-xs font-medium transition-colors",
        active
          ? "bg-accent text-accent-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

export function FilterChip({ label }: { label: string }) {
  return (
    <span className="inline-flex h-7 items-center rounded-md border bg-background px-2.5 text-muted-foreground">
      {label}
    </span>
  );
}
