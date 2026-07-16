"use client";

import { useTheme } from "next-themes";

import { getCategoryAccentStyle } from "@/lib/category-colors";
import { cn } from "@/lib/utils";

export function CategoryAccent({
  color,
  size = "md",
  subtle = false,
  className,
}: {
  color?: string | null;
  size?: "xs" | "sm" | "md";
  subtle?: boolean;
  className?: string;
}) {
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";
  const accentColor = color ?? "#64748b";
  const style = getCategoryAccentStyle(accentColor, theme);
  const sizeClasses = {
    xs: "h-3 w-3 rounded-[4px]",
    sm: "h-4 w-4 rounded-md",
    md: "h-7 w-7 rounded-lg",
  }[size];
  const innerClasses = {
    xs: "h-1 w-1 rounded-[1px]",
    sm: "h-1.5 w-1.5 rounded-[2px]",
    md: "h-2.5 w-2.5 rounded-[3px]",
  }[size];

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center border border-border",
        sizeClasses,
        subtle && "opacity-60",
        className,
      )}
      style={{ backgroundColor: style.backgroundColor }}
      aria-hidden="true"
    >
      <span
        className={cn("shadow-sm", innerClasses)}
        style={{
          backgroundColor: accentColor,
          boxShadow: style.innerOutline
            ? `0 0 0 1px ${style.innerOutline}`
            : undefined,
        }}
      />
    </span>
  );
}

export function CategoryCompactAccent({
  color,
  className,
}: {
  color?: string | null;
  className?: string;
}) {
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";
  const accentColor = color ?? "#64748b";
  const style = getCategoryAccentStyle(accentColor, theme);

  return (
    <span
      className={cn("h-3 w-3 shrink-0 rounded-[3px]", className)}
      style={{
        backgroundColor: accentColor,
        boxShadow: style.innerOutline
          ? `0 0 0 1px ${style.innerOutline}`
          : undefined,
      }}
      aria-hidden="true"
    />
  );
}
