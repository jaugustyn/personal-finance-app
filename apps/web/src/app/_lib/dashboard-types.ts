import type { Direction } from "@/lib/api";

export type DashboardRange = "1m" | "3m" | "6m" | "12m" | "all";
export type DashboardDirection = Exclude<Direction, "all">;
export type DashboardLimit = 5 | 8 | 12;
export type DashboardTab = "overview" | "review" | "explore";

export const RANGE_MONTHS: Record<DashboardRange, number> = {
  "1m": 1,
  "3m": 3,
  "6m": 6,
  "12m": 12,
  all: 12,
};

export const RANGE_OPTIONS: DashboardRange[] = ["1m", "3m", "6m", "12m", "all"];
export const LIMIT_OPTIONS: DashboardLimit[] = [5, 8, 12];
