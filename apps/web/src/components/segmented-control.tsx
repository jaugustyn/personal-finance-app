"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SegmentedControlOption {
  value: string;
  label: string;
  tooltip?: string;
}

export function SegmentedControl({
  value,
  options,
  onValueChange,
  ariaLabel,
  className,
}: {
  value: string;
  options: readonly SegmentedControlOption[];
  onValueChange: (value: string) => void;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex h-9 max-w-full items-stretch divide-x divide-border/60 overflow-hidden rounded-md border border-input bg-card",
        className,
      )}
    >
      {options.map((option) => {
        const active = option.value === value;
        const button = (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onValueChange(option.value)}
            className={cn(
              "relative flex h-full items-center whitespace-nowrap px-3 text-xs font-medium leading-none transition-colors focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              active
                ? "bg-accent-soft text-accent-soft-foreground"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        );

        if (!option.tooltip) {
          return button;
        }

        return (
          <Tooltip key={option.value}>
            <TooltipTrigger asChild>{button}</TooltipTrigger>
            <TooltipContent
              side="bottom"
              className="max-w-xs text-pretty leading-relaxed"
            >
              {option.tooltip}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
