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
      className="toaster group [--width:31rem]"
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
        classNames: {
          toast:
            "group toast group-[.toaster]:relative group-[.toaster]:min-h-[4.75rem] group-[.toaster]:max-w-[calc(100vw-2rem)] group-[.toaster]:rounded-lg group-[.toaster]:border group-[.toaster]:border-l-4 group-[.toaster]:border-border group-[.toaster]:border-l-border group-[.toaster]:bg-card group-[.toaster]:px-5 group-[.toaster]:py-4 group-[.toaster]:pr-12 group-[.toaster]:text-card-foreground group-[.toaster]:shadow-[0_18px_45px_-28px_hsl(var(--foreground)/0.55),0_8px_24px_-18px_hsl(var(--foreground)/0.25)]",
          content: "group-[.toast]:gap-1.5",
          icon:
            "group-[.toast]:mt-0.5 group-[.toast]:flex group-[.toast]:h-8 group-[.toast]:w-8 group-[.toast]:items-center group-[.toast]:justify-center group-[.toast]:rounded-md group-[.toast]:bg-muted/60",
          title:
            "group-[.toast]:text-[15px] group-[.toast]:font-semibold group-[.toast]:leading-5 group-[.toast]:tracking-normal group-[.toast]:text-foreground",
          description:
            "group-[.toast]:text-sm group-[.toast]:leading-5 group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:h-8 group-[.toast]:rounded-md group-[.toast]:border group-[.toast]:border-border group-[.toast]:bg-background group-[.toast]:px-3 group-[.toast]:text-sm group-[.toast]:font-medium group-[.toast]:text-foreground group-[.toast]:shadow-sm group-[.toast]:hover:bg-muted",
          cancelButton:
            "group-[.toast]:h-8 group-[.toast]:rounded-md group-[.toast]:bg-muted group-[.toast]:px-3 group-[.toast]:text-sm group-[.toast]:font-medium group-[.toast]:text-muted-foreground group-[.toast]:hover:bg-muted/80",
          closeButton:
            "group-[.toast]:!left-auto group-[.toast]:!right-2 group-[.toast]:!top-2 group-[.toast]:!h-7 group-[.toast]:!w-7 group-[.toast]:!translate-x-0 group-[.toast]:!translate-y-0 group-[.toast]:!rounded-md group-[.toast]:!border-0 group-[.toast]:!bg-transparent group-[.toast]:!text-muted-foreground group-[.toast]:!shadow-none group-[.toast]:hover:!bg-muted group-[.toast]:hover:!text-foreground",
          success:
            "group-[.toaster]:!border-l-positive group-[.toaster]:bg-card",
          info: "group-[.toaster]:!border-l-info group-[.toaster]:bg-card",
          warning:
            "group-[.toaster]:!border-l-warning group-[.toaster]:bg-card",
          error:
            "group-[.toaster]:!border-l-destructive group-[.toaster]:bg-card",
        },
      }}
      {...props}
    />
  );
}
