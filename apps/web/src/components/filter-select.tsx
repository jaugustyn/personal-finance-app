"use client";

import type { ReactNode } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface FilterSelectOption {
  value: string;
  label: string;
  leading?: ReactNode;
  muted?: boolean;
}

export function FilterSelect({
  id,
  value,
  onValueChange,
  options,
  ariaLabel,
  className,
  contentClassName,
  disabled,
  placeholder,
}: {
  id?: string;
  value: string;
  onValueChange: (value: string) => void;
  options: FilterSelectOption[];
  ariaLabel?: string;
  className?: string;
  contentClassName?: string;
  disabled?: boolean;
  placeholder?: string;
}) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger
        id={id}
        className={cn("w-full", className)}
        aria-label={ariaLabel}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className={contentClassName}>
        {options.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            indicatorPosition="right"
          >
            <span
              className={cn(
                "flex min-w-0 items-center gap-2",
                option.muted && "text-muted-foreground",
              )}
            >
              {option.leading}
              <span className="truncate">{option.label}</span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
