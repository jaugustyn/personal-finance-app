"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { AppUtilities } from "@/components/app-utilities";
import { LogoMark } from "@/components/logo-mark";
import { api, type AttentionSummary } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { NAV_SECTIONS } from "@/lib/nav";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

/** Shared nav body used by both the desktop sidebar and the mobile sheet. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { t } = useT();
  const attention = useQuery({
    queryKey: queryKeys.attention.summary,
    queryFn: api.attentionSummary,
    staleTime: 60_000,
  });

  return (
    <nav className="flex-1 space-y-6 overflow-y-auto p-3">
      {NAV_SECTIONS.map((section) => (
        <div key={section.titleKey} className="space-y-0.5">
          <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/85">
            {t(section.titleKey)}
          </p>
          {section.items.map((it) => {
            const active =
              pathname === it.href ||
              (it.href !== "/" && pathname.startsWith(`${it.href}/`));
            const Icon = it.icon;
            const count = attention.data
              ? attentionCount(attention.data, it.href)
              : 0;

            return (
              <Link
                key={it.href}
                href={it.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative flex min-h-10 items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary/[0.09] font-medium text-foreground dark:bg-primary/[0.12]"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {active && (
                  <span className="absolute inset-y-0 left-0 w-[3px] bg-primary/65" />
                )}
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    active ? "text-primary" : "group-hover:text-foreground",
                  )}
                />
                <span className="min-w-0 flex-1 truncate">
                  {t(it.labelKey)}
                </span>
                {count > 0 ? (
                  <span
                    className={cn(
                      "inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md px-1.5 text-[10px] font-semibold tabular-nums",
                      active
                        ? "bg-primary/15 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                    title={t("nav.pendingItems", { count })}
                    aria-label={t("nav.pendingItems", { count })}
                  >
                    {count > 99 ? "99+" : count}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function SidebarBrand() {
  const { t } = useT();

  return (
    <Link
      href="/"
      className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border/70 px-5 outline-none transition-colors hover:bg-accent/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
    >
      <LogoMark className="h-8 w-8 text-primary" />
      <span className="text-base font-semibold tracking-tight text-foreground">
        {t("app.title")}
      </span>
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border/70 bg-sidebar text-sidebar-foreground md:flex">
      <SidebarBrand />
      <SidebarNav />
      <div className="flex shrink-0 items-center justify-center border-t border-border/70 px-4 py-3">
        <AppUtilities variant="sidebar" className="w-full justify-center" />
      </div>
    </aside>
  );
}

function attentionCount(summary: AttentionSummary, href: string) {
  if (href === "/transactions") return summary.transaction_reviews;
  if (href === "/subscriptions") return summary.subscription_reviews;
  if (href === "/anomalies") return summary.anomaly_reviews;
  if (href === "/assets") return summary.asset_reviews;
  return 0;
}
