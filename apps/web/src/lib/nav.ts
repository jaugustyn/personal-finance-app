import {
  LayoutDashboard,
  Receipt,
  TrendingUp,
  AlertTriangle,
  Repeat,
  PiggyBank,
  Upload,
  Tag,
  Store,
  Settings,
  Sparkles,
  CalendarRange,
  CircleDollarSign,
  BrainCircuit,
  Landmark,
  type LucideIcon,
} from "lucide-react";
import type { TranslationKey } from "@/lib/i18n";

export interface NavItem {
  href: string;
  labelKey: TranslationKey;
  icon: LucideIcon;
}

export interface NavSection {
  titleKey: TranslationKey;
  items: NavItem[];
}

/** Single source of truth for desktop and mobile navigation. */
export const NAV_SECTIONS: NavSection[] = [
  {
    titleKey: "nav.section.overview",
    items: [
      { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
      { href: "/transactions", labelKey: "nav.transactions", icon: Receipt },
      { href: "/assets", labelKey: "nav.assets", icon: PiggyBank },
    ],
  },
  {
    titleKey: "nav.section.money",
    items: [
      { href: "/accounts", labelKey: "nav.accounts", icon: Landmark },
      { href: "/imports", labelKey: "nav.imports", icon: Upload },
      { href: "/categories", labelKey: "nav.categories", icon: Tag },
      { href: "/merchants", labelKey: "nav.merchants", icon: Store },
      { href: "/currencies", labelKey: "nav.currencies", icon: CircleDollarSign },
    ],
  },
  {
    titleKey: "nav.section.analysisPlanning",
    items: [
      { href: "/recap", labelKey: "nav.recap", icon: CalendarRange },
      { href: "/subscriptions", labelKey: "nav.subscriptions", icon: Repeat },
      { href: "/anomalies", labelKey: "nav.anomalies", icon: AlertTriangle },
      { href: "/forecast", labelKey: "nav.forecast", icon: TrendingUp },
    ],
  },
  {
    titleKey: "nav.section.more",
    items: [
      { href: "/assistant", labelKey: "nav.assistant", icon: Sparkles },
      { href: "/ml", labelKey: "nav.ml", icon: BrainCircuit },
      { href: "/settings", labelKey: "nav.settings", icon: Settings },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items);
