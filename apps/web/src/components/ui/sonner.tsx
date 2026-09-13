"use client";

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

export function Toaster(props: ToasterProps) {
  const { theme = "system" } = useTheme();
  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster"
      style={{ width: "min(24rem, calc(100vw - 2rem))" }}
      position="top-right"
      duration={6_000}
      closeButton
      icons={{
        success: <CheckCircle2 className="h-5 w-5 text-positive" />,
        info: <Info className="h-5 w-5 text-info" />,
        warning: <AlertTriangle className="h-5 w-5 text-warning" />,
        error: <AlertCircle className="h-5 w-5 text-destructive" />,
        loading: (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ),
      }}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "toast pointer-events-auto flex w-full items-center gap-3 rounded-lg border bg-popover p-4 pr-12 text-popover-foreground shadow-lg [&[data-expanded=false][data-front=false]>*]:opacity-0",
          content: "flex min-w-0 flex-1 flex-col gap-1",
          icon: "flex h-5 w-5 shrink-0 items-center justify-center",
          title: "text-sm font-medium leading-5",
          description: "text-sm leading-5 text-muted-foreground",
          actionButton:
            "shrink-0 rounded-md border bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          cancelButton:
            "shrink-0 rounded-md bg-muted px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          closeButton:
            "absolute right-3 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md border-0 bg-transparent! p-0 text-muted-foreground! hover:bg-muted! hover:text-foreground! focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&>svg]:h-4 [&>svg]:w-4",
          success:
            "border-positive/40 bg-[linear-gradient(hsl(var(--positive)/0.10),hsl(var(--positive)/0.10))]",
          info: "border-info/40 bg-[linear-gradient(hsl(var(--info)/0.10),hsl(var(--info)/0.10))]",
          warning:
            "border-warning/40 bg-[linear-gradient(hsl(var(--warning)/0.10),hsl(var(--warning)/0.10))]",
          error:
            "border-destructive/40 bg-[linear-gradient(hsl(var(--destructive)/0.10),hsl(var(--destructive)/0.10))]",
        },
      }}
      {...props}
    />
  );
}
