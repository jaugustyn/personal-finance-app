"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ClearableInputProps = Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "onChange"
> & {
  value: string;
  onValueChange: (value: string) => void;
  clearLabel: string;
  inputClassName?: string;
  leftIcon?: React.ReactNode;
};

export const ClearableInput = React.forwardRef<
  HTMLInputElement,
  ClearableInputProps
>(
  (
    {
      value,
      onValueChange,
      clearLabel,
      className,
      inputClassName,
      leftIcon,
      disabled,
      autoComplete,
      ...props
    },
    ref,
  ) => (
    <div className={cn("relative", className)}>
      {leftIcon ? (
        <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
          {leftIcon}
        </div>
      ) : null}
      <Input
        ref={ref}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        autoComplete={autoComplete ?? "off"}
        disabled={disabled}
        className={cn(
          leftIcon ? "pl-9" : "",
          value && !disabled ? "pr-9" : "",
          inputClassName,
        )}
        {...props}
      />
      {value && !disabled ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          onClick={() => onValueChange("")}
          aria-label={clearLabel}
        >
          <X className="h-4 w-4" />
        </Button>
      ) : null}
    </div>
  ),
);
ClearableInput.displayName = "ClearableInput";
