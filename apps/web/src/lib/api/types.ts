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
  category?: string | null;
}

export interface CategoryTrendPoint {
  month: string;
  category: string;
  amount: number;
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
  subcategory: string | null;
  category_source: string | null;
  category_predicted: string | null;
  category_confidence: number | null;
  category_predicted_source: string | null;
  category_suggestion_rejected: boolean;
  transaction_type: string;
  source: string;
  is_transfer?: boolean;
  notes?: string | null;
  tags?: string[];
  import_id?: number | null;
}

export interface CategoryDef {
  id: number;
  name: string;
  is_system: boolean;
  parent: string | null;
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

export interface ReviewSummary {
  counts: {
    uncategorized: number;
    no_suggestion: number;
    low_confidence: number;
    ready_to_accept: number;
    rejected: number;
    categorized: number;
  };
  rare_classes: { category: string; count: number }[];
  recurring_unruled: { merchant: string; count: number }[];
  feedback_quality: Record<string, unknown>;
  confusion_hotspots: Record<string, unknown>[];
  anomaly_feedback: Record<string, unknown>;
  subscription_feedback: Record<string, unknown>;
  confidence_threshold: number;
  rare_class_threshold: number;
}

export interface Recap {
  period: "week" | "month" | "custom";
  current_from: string;
  current_to: string;
  previous_from: string;
  previous_to: string;
  cashflow: {
    income: number;
    expenses: number;
    net: number;
    income_delta: number;
    expenses_delta: number;
    net_delta: number;
  };
  category_changes: {
    category: string;
    current: number;
    previous: number;
    delta: number;
  }[];
  top_merchants: { merchant: string; amount: number; count: number }[];
  limit_breaches: {
    category: string;
    spent: number;
    limit: number;
    overshoot: number;
  }[];
  savings_progress: {
    goal: number;
    net: number;
    ratio: number;
    met: boolean;
  } | null;
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
  priority_score: number;
  anomaly_type: string;
  reasons: string[];
  reason_codes: string[];
  merchant_occurrences: number;
  merchant_median_amount: number;
  is_recurring_merchant: boolean;
  feedback_status: "relevant" | "not_relevant" | "ignore_merchant" | null;
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
  field_specs: {
    key: string;
    required: boolean;
    recommended: boolean;
    description: string;
  }[];
  quality_warnings: string[];
  supported_extensions: string[];
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

export interface MlMetricSummary {
  model: string | null;
  macro_f1: number | null;
  weighted_f1: number | null;
  coverage_at_055: number | null;
  accuracy_at_055: number | null;
}

export interface MlModelComparison {
  estimator: string;
  feature_set: string;
  rank: number | null;
  macro_f1: number | null;
  weighted_f1: number | null;
  coverage_at_055: number | null;
  accuracy_at_055: number | null;
  time_holdout_macro_f1: number | null;
  merchant_group_macro_f1: number | null;
  stability_score: number | null;
  confidence_note: string | null;
  skipped: boolean;
  error: string | null;
  is_recommended: boolean;
  is_current: boolean;
}

export interface MlModelRecommendation {
  estimator: string;
  feature_set: string;
  reason_code: string;
  action_codes: string[];
  warning_codes: string[];
  macro_f1: number | null;
  weighted_f1: number | null;
  coverage_at_055: number | null;
  accuracy_at_055: number | null;
  confidence_threshold: number;
  based_on_report: boolean;
  feature_decision_reason: string | null;
}

export interface MlModelStatus {
  exists: boolean;
  path: string;
  updated_at: string | null;
  estimator: string | null;
  feature_set: string | null;
  classes: string[];
  known_categories: string[];
  missing_categories: string[];
  extra_classes: string[];
  n_total_labelled: number | null;
  n_classes: number | null;
  report_path: string | null;
  report_updated_at: string | null;
  best_model: MlMetricSummary | null;
  load_error: string | null;
}

export interface MlReadiness {
  level: string;
  total_labelled: number;
  minimum_total: number;
  recommended_total: number;
  ideal_total: number;
  minimum_per_category: number;
  recommended_per_category: number;
  strong_per_category: number;
  category_counts: Record<string, number>;
  below_minimum_per_category: string[];
  below_recommended_per_category: string[];
  date_span_months: number | null;
  recommended_history_months: string;
  training_labels_source: string;
  category_predicted_is_ground_truth: boolean;
  next_review_priority: string[];
}

export interface MlLatestReport {
  path: string | null;
  updated_at: string | null;
  report: Record<string, unknown> | null;
}

export interface MlDashboard {
  status: MlModelStatus;
  readiness: MlReadiness;
  latest_report: MlLatestReport;
  model_comparison: MlModelComparison[];
  recommendation: MlModelRecommendation;
  validation_slices: Record<string, unknown>;
  confidence_policy: Record<string, unknown>;
  feedback_quality: Record<string, unknown>;
  confusion_hotspots: Record<string, unknown>[];
}

export interface MlComparison {
  models: MlModelComparison[];
  recommendation: MlModelRecommendation;
}

export interface MlRetrainResponse {
  status: string;
  message: string;
}

export interface MlReclassifyResponse {
  updated: number;
}

export interface MlFeedbackInput {
  event_type: string;
  transaction_id?: number | null;
  entity_type?: string | null;
  entity_key?: string | null;
  predicted_category?: string | null;
  final_category?: string | null;
  confidence?: number | null;
  source?: string | null;
  model_artifact?: string | null;
}

export interface MlFeedbackResponse {
  id: number | null;
  status: string;
}

export interface ChatRequest {
  question: string;
  use_llm_summary?: boolean;
  previous_tool?: string | null;
  previous_tool_args?: Record<string, unknown> | null;
}

export interface ChatResponse {
  answer: string;
  tool: string | null;
  tool_args: Record<string, unknown> | null;
  data: Record<string, unknown> | null;
  source: string;
}

export interface ChatHealthResponse {
  ollama_available: boolean;
  llm_enabled: boolean;
  mode: "hybrid" | "deterministic";
  deterministic_tools: string[];
}
