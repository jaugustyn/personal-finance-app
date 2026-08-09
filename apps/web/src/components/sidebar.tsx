"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { NAV_SECTIONS } from "@/lib/nav";
import { api, type AttentionSummary } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

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
    <nav className="flex-1 space-y-5 overflow-y-auto p-3">
      {NAV_SECTIONS.map((section) => (
        <div key={section.titleKey} className="space-y-1">
          <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
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
                  "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-accent-soft font-medium text-accent-soft-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                )}
                <Icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{t(it.labelKey)}</span>
                {count > 0 ? (
                  <span
                    className={cn(
                      "inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md px-1.5 text-[10px] font-semibold tabular-nums",
                      active
                        ? "bg-background/75 text-foreground"
                        : "bg-primary/10 text-primary",
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
    <div className="flex h-14 items-center gap-2 border-b px-4 font-semibold">
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Wallet className="h-4 w-4" />
      </span>
      <span className="tracking-tight">{t("app.title")}</span>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground md:flex">
      <SidebarBrand />
      <SidebarNav />
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
