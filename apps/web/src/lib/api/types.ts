export type Direction = "debit" | "credit" | "all";
export type CategoryState =
  | "all"
  | "categorized"
  | "uncategorized"
  | "suggested"
  | "needs_review"
  | "rejected";

export interface OverviewStats {
  period_from: string | null;
  period_to: string | null;
  total_income: number;
  total_expenses: number;
  net_cashflow: number;
  savings_rate: number;
  tx_count: number;
}

export interface CashflowPoint {
  month: string;
  income: number;
  expenses: number;
  net: number;
}

export interface CategoryBreakdown {
  category: string | null;
  amount: number;
  count: number;
  share: number;
}

export interface NetWorthPoint {
  month: string;
  balance: number;
}

export interface MerchantStat {
  merchant: string;
  amount: number;
  count: number;
}

export interface Transaction {
  id: number;
  booking_date: string;
  merchant: string;
  title: string;
  amount: number;
  currency: string;
  direction: "debit" | "credit";
  category: string | null;
  category_source: string | null;
  category_predicted: string | null;
  category_confidence: number | null;
  category_predicted_source: string | null;
  category_suggestion_rejected: boolean;
  transaction_type: string;
  source: string;
  is_transfer?: boolean;
  import_id?: number | null;
}

export interface CategoryDef {
  id: number;
  name: string;
  is_system: boolean;
  color: string | null;
  icon: string | null;
  usage_count: number;
}

export interface MerchantGroup {
  merchant: string;
  count: number;
  total_debit: number | string;
  total_credit: number | string;
  common_category: string | null;
  sample_titles: string[];
}

export interface ImportHistoryRow {
  id: number;
  source: string;
  filename: string;
  total_rows: number;
  inserted: number;
  duplicates: number;
  created_at: string;
}

export interface ForecastPoint {
  month: string;
  amount: number;
}

export interface ForecastResponse {
  category: string | null;
  model: string;
  horizon: number;
  mape: number | null;
  rmse: number | null;
  history: ForecastPoint[];
  forecast: ForecastPoint[];
}

export interface Anomaly {
  id: number;
  booking_date: string;
  merchant: string;
  title: string;
  amount: number;
  direction: "debit" | "credit";
  category: string | null;
  severity: number;
  reasons: string[];
}

export interface Subscription {
  merchant: string;
  cadence: string;
  median_amount: number;
  occurrences: number;
  last_seen: string;
  estimated_monthly_cost: number;
  confidence: number;
}

export interface Asset {
  id: number;
  symbol: string;
  name: string;
  asset_class: string;
  currency: string;
  quantity: number | string;
  cost_basis: number | string;
  notes: string | null;
  last_price: number | string | null;
  last_value_pln: number | string | null;
  last_snapshot_date: string | null;
  pnl_pln: number | string | null;
}

export interface PortfolioSummary {
  total_value_pln: number | string;
  total_cost_pln: number | string;
  pnl_pln: number | string;
  pnl_pct: number;
  asset_count: number;
  last_refresh: string | null;
}

export interface AssetHistoryPoint {
  snapshot_date: string;
  value_pln: number | string;
}

export interface SankeyNode {
  name: string;
}

export interface SankeyLink {
  source: number;
  target: number;
  value: number | string;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
}

export interface AssetInput {
  symbol: string;
  name?: string;
  asset_class?: string;
  currency?: string;
  quantity?: number;
  cost_basis?: number;
  notes?: string | null;
}

export interface ImportPreview {
  headers: string[];
  sample_rows: Record<string, string>[];
  delimiter: string;
  encoding: string;
  detected_source: string | null;
  detected_mapping: Record<string, string | null>;
}

export interface ImportSummary {
  import_id: number;
  source: string;
  inserted: number;
  duplicates: number;
  total_rows: number;
}

export interface UserProfile {
  id: number;
  base_currency: string;
  salary_day: number | null;
  monthly_savings_goal: number | string | null;
  category_limits: Record<string, number>;
  created_at: string | null;
}

export interface UserProfileInput {
  base_currency?: string | null;
  salary_day?: number | null;
  monthly_savings_goal?: number | null;
  category_limits?: Record<string, number>;
}

export interface PersonalRule {
  id: number;
  pattern: string;
  pattern_norm: string;
  pattern_target: "merchant" | "title" | "both";
  category: string | null;
  transaction_type: string | null;
  is_transfer: boolean | null;
  priority: number;
  active: boolean;
  mode: "suggest_only" | "auto_apply";
  confidence: number;
  created_at: string | null;
}

export interface PersonalRuleInput {
  pattern: string;
  pattern_target?: "merchant" | "title" | "both";
  category?: string | null;
  transaction_type?: string | null;
  is_transfer?: boolean | null;
  priority?: number;
  active?: boolean;
  mode?: "suggest_only" | "auto_apply";
  confidence?: number;
}
