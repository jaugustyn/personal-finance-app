"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  pageTabClassName,
  pageTabsListClassName,
} from "@/components/page-tabs";
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
    <nav
      className={pageTabsListClassName}
      aria-label={t("assets.sectionNavigation")}
    >
      {tabs.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={pageTabClassName(active)}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
