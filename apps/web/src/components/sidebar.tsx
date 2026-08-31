"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { AppUtilities } from "@/components/app-utilities";
import { LogoMark } from "@/components/logo-mark";
import { api, type AttentionSummary } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { NAV_SECTIONS, SETTINGS_NAV_ITEM } from "@/lib/nav";
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
    <nav className="flex-1 space-y-5 overflow-y-auto px-2 py-2 [@media(max-height:850px)]:space-y-4">
      {NAV_SECTIONS.map((section) => (
        <div
          key={section.titleKey ?? "primary"}
          className="space-y-1"
        >
          {section.titleKey ? (
            <p className="px-4 pb-1 text-xs font-semibold uppercase tracking-[0.08em] text-foreground/65 dark:text-foreground/70 [@media(max-height:850px)]:pb-0.5">
              {t(section.titleKey)}
            </p>
          ) : null}
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
                  "group relative flex min-h-[38px] items-center gap-3 overflow-hidden rounded-[6px] px-4 py-1 text-[15px] font-normal leading-5 tracking-[-0.01em] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [@media(max-height:850px)]:min-h-9",
                  active
                    ? "bg-primary/[0.055] font-medium text-foreground dark:bg-primary/[0.09]"
                    : "text-foreground/[0.68] hover:bg-foreground/[0.018] hover:text-foreground dark:text-foreground/70 dark:hover:bg-foreground/[0.03]",
                )}
              >
                <Icon
                  className={cn(
                    "h-[17px] w-[17px] shrink-0 transition-colors",
                    active ? "text-primary" : "group-hover:text-foreground",
                  )}
                />
                <span className="min-w-0 flex-1 truncate">
                  {t(it.labelKey)}
                </span>
                {count > 0 ? (
                  <span
                    className={cn(
                      "inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md px-1.5 text-[11px] font-semibold tabular-nums",
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
      <span className="text-lg font-semibold tracking-tight text-foreground">
        {t("app.title")}
      </span>
    </Link>
  );
}

export function SidebarSettingsLink({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const { t } = useT();
  const active =
    pathname === SETTINGS_NAV_ITEM.href ||
    pathname.startsWith(`${SETTINGS_NAV_ITEM.href}/`);
  const Icon = SETTINGS_NAV_ITEM.icon;

  return (
    <Link
      href={SETTINGS_NAV_ITEM.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex h-[38px] items-center gap-3 rounded-[6px] px-4 text-[15px] font-normal tracking-[-0.01em] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        active
          ? "bg-primary/[0.055] font-medium text-foreground dark:bg-primary/[0.09]"
          : "text-foreground/[0.68] hover:bg-foreground/[0.018] hover:text-foreground dark:text-foreground/70 dark:hover:bg-foreground/[0.03]",
      )}
    >
      <Icon
        className={cn(
          "h-[17px] w-[17px] shrink-0 transition-colors",
          active ? "text-primary" : "group-hover:text-foreground",
        )}
      />
      <span className="min-w-0 flex-1 truncate">
        {t(SETTINGS_NAV_ITEM.labelKey)}
      </span>
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border/70 bg-sidebar text-sidebar-foreground md:flex">
      <SidebarBrand />
      <SidebarNav />
      <div className="relative shrink-0 space-y-1 border-t border-border/80 bg-sidebar px-2 py-2.5">
        <AppUtilities variant="sidebar" className="w-full" />
        <SidebarSettingsLink />
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
