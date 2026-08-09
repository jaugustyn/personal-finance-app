"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { useT, type TranslationKey } from "@/lib/i18n";
import { NAV_ITEMS } from "@/lib/nav";

const NESTED_PAGE_TITLES: Partial<Record<string, TranslationKey>> = {
  "/assets/analysis": "assets.tab.analytics",
  "/assets/archive": "assets.tab.archive",
};

export function DocumentTitle() {
  const pathname = usePathname();
  const { t } = useT();
  const title = t(titleKeyForPath(pathname));

  useEffect(() => {
    document.title = title;
  }, [title]);

  return null;
}

function titleKeyForPath(pathname: string): TranslationKey {
  const nestedTitle = NESTED_PAGE_TITLES[pathname];
  if (nestedTitle) return nestedTitle;

  const item = NAV_ITEMS.find(
    ({ href }) =>
      pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)),
  );
  return item?.labelKey ?? "app.title";
}
