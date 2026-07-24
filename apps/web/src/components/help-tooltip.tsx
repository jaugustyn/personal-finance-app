"use client";

import { cloneElement, type ReactElement, type ReactNode } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface HelpTooltipProps {
  content: ReactNode;
  children: ReactElement<{
    className?: string;
    tabIndex?: number;
  }>;
  className?: string;
  contentClassName?: string;
}

/** Compact contextual help for labels and existing status elements. */
export function HelpTooltip({
  content,
  children,
  className,
  contentClassName,
}: HelpTooltipProps) {
  const trigger = cloneElement(children, {
    className: cn(
      children.props.className,
      "cursor-help focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
      className,
    ),
    tabIndex: children.props.tabIndex ?? 0,
  });

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {trigger}
      </TooltipTrigger>
      <TooltipContent
        className={cn("max-w-72 leading-relaxed", contentClassName)}
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );
}
