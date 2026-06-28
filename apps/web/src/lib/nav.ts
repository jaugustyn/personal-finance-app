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
  ClipboardCheck,
  CalendarRange,
  CircleDollarSign,
  BrainCircuit,
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

/** Single source of truth for navigation, shared by sidebar, mobile nav and ⌘K. */
export const NAV_SECTIONS: NavSection[] = [
  {
    titleKey: "nav.section.overview",
    items: [
      { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
      { href: "/transactions", labelKey: "nav.transactions", icon: Receipt },
    ],
  },
  {
    titleKey: "nav.section.money",
    items: [
      { href: "/imports", labelKey: "nav.imports", icon: Upload },
      { href: "/categories", labelKey: "nav.categories", icon: Tag },
      { href: "/merchants", labelKey: "nav.merchants", icon: Store },
      { href: "/currencies", labelKey: "nav.currencies", icon: CircleDollarSign },
      { href: "/review", labelKey: "nav.review", icon: ClipboardCheck },
      { href: "/ml", labelKey: "nav.ml", icon: BrainCircuit },
    ],
  },
  {
    titleKey: "nav.section.insights",
    items: [
      { href: "/forecast", labelKey: "nav.forecast", icon: TrendingUp },
      { href: "/recap", labelKey: "nav.recap", icon: CalendarRange },
      { href: "/anomalies", labelKey: "nav.anomalies", icon: AlertTriangle },
      { href: "/subscriptions", labelKey: "nav.subscriptions", icon: Repeat },
      { href: "/assets", labelKey: "nav.assets", icon: PiggyBank },
    ],
  },
  {
    titleKey: "nav.section.more",
    items: [
      { href: "/assistant", labelKey: "nav.assistant", icon: Sparkles },
      { href: "/settings", labelKey: "nav.settings", icon: Settings },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items);
