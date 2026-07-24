"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function AssetSectionTabs() {
  const pathname = usePathname();
  const { t } = useT();
  const tabs = [
    { href: "/assets", label: t("assets.tab.portfolio") },
    { href: "/assets/analysis", label: t("assets.tab.analytics") },
    { href: "/assets/archive", label: t("assets.tab.archive") },
  ];

  return (
    <nav className="flex gap-6 border-b" aria-label={t("assets.sectionNavigation")}>
      {tabs.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-0.5 pb-3 text-sm font-medium transition-colors",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
