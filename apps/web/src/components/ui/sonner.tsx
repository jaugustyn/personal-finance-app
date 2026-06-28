"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

export function Toaster(props: ToasterProps) {
  const { theme = "system" } = useTheme();
  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      position="top-right"
      duration={5_000}
      richColors
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:min-w-80 group-[.toaster]:max-w-md group-[.toaster]:rounded-lg group-[.toaster]:px-4 group-[.toaster]:py-3 group-[.toaster]:text-sm group-[.toaster]:shadow-lg",
          title: "group-[.toast]:text-sm group-[.toast]:font-medium",
          description: "group-[.toast]:text-sm group-[.toast]:opacity-85",
          actionButton:
            "group-[.toast]:border group-[.toast]:border-border group-[.toast]:bg-background group-[.toast]:text-foreground group-[.toast]:shadow-sm group-[.toast]:hover:bg-muted",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
}
