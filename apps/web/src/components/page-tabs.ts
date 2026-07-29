import { cn } from "@/lib/utils";

export const pageTabsListClassName =
  "flex h-11 w-full max-w-full justify-start overflow-x-auto overflow-y-hidden rounded-none border-b bg-transparent p-0";

const pageTabBaseClassName =
  "inline-flex h-11 shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring";

export function pageTabClassName(active: boolean) {
  return cn(
    pageTabBaseClassName,
    active
      ? "border-primary text-foreground"
      : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
  );
}

export const pageTabTriggerClassName = cn(
  pageTabBaseClassName,
  "justify-center rounded-none border-transparent py-0 shadow-none data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none data-[state=inactive]:text-muted-foreground data-[state=inactive]:hover:border-border data-[state=inactive]:hover:text-foreground",
);
