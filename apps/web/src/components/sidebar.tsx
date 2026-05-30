"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Receipt,
  TrendingUp,
  AlertTriangle,
  Repeat,
  Wallet,
  PiggyBank,
  Upload,
  Tag,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useT, type TranslationKey } from "@/lib/i18n";

const items: { href: string; labelKey: TranslationKey; icon: typeof Wallet }[] =
  [
    { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
    { href: "/transactions", labelKey: "nav.transactions", icon: Receipt },
    { href: "/categories", labelKey: "nav.categories", icon: Tag },
    { href: "/imports", labelKey: "nav.imports", icon: Upload },
    { href: "/assets", labelKey: "nav.assets", icon: PiggyBank },
    { href: "/forecast", labelKey: "nav.forecast", icon: TrendingUp },
    { href: "/anomalies", labelKey: "nav.anomalies", icon: AlertTriangle },
    { href: "/subscriptions", labelKey: "nav.subscriptions", icon: Repeat },
    { href: "/settings", labelKey: "nav.settings", icon: Settings },
  ];

export function Sidebar() {
  const pathname = usePathname();
  const { t } = useT();
  return (
    <aside className="hidden md:flex w-60 flex-col border-r bg-card">
      <div className="flex h-14 items-center gap-2 border-b px-4 font-semibold">
        <Wallet className="h-5 w-5" />
        <span>{t("app.title")}</span>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {items.map((it) => {
          const active = pathname === it.href;
          const Icon = it.icon;
          return (
            <Link
              key={it.href}
              href={it.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-secondary text-secondary-foreground font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {t(it.labelKey)}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3 text-xs text-muted-foreground">
        <a
          href={
            process.env.NEXT_PUBLIC_LEGACY_UI_URL ?? "http://localhost:8501"
          }
          target="_blank"
          rel="noreferrer"
          className="hover:text-foreground"
        >
          {t("nav.labUi")}
        </a>
      </div>
    </aside>
  );
}
