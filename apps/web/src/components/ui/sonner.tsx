"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

export function Toaster(props: ToasterProps) {
  const { theme = "system" } = useTheme();
  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group [--width:28rem]"
      position="top-right"
      duration={6_000}
      closeButton
      richColors
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:min-h-16 group-[.toaster]:max-w-[calc(100vw-2rem)] group-[.toaster]:rounded-lg group-[.toaster]:border group-[.toaster]:px-5 group-[.toaster]:py-4 group-[.toaster]:text-sm group-[.toaster]:shadow-xl group-[.toaster]:backdrop-blur",
          content: "group-[.toast]:gap-1.5",
          title:
            "group-[.toast]:text-[15px] group-[.toast]:font-semibold group-[.toast]:leading-5",
          description:
            "group-[.toast]:text-sm group-[.toast]:leading-5 group-[.toast]:opacity-90",
          actionButton:
            "group-[.toast]:h-8 group-[.toast]:rounded-md group-[.toast]:border group-[.toast]:border-border group-[.toast]:bg-background group-[.toast]:px-3 group-[.toast]:text-sm group-[.toast]:font-medium group-[.toast]:text-foreground group-[.toast]:shadow-sm group-[.toast]:hover:bg-muted",
          cancelButton:
            "group-[.toast]:h-8 group-[.toast]:rounded-md group-[.toast]:bg-muted group-[.toast]:px-3 group-[.toast]:text-sm group-[.toast]:font-medium group-[.toast]:text-muted-foreground group-[.toast]:hover:bg-muted/80",
          closeButton:
            "group-[.toast]:border-border group-[.toast]:bg-background group-[.toast]:text-muted-foreground group-[.toast]:shadow-sm group-[.toast]:hover:bg-muted group-[.toast]:hover:text-foreground",
        },
      }}
      {...props}
    />
  );
}
