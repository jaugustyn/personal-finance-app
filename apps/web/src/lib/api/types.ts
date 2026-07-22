export type Direction = "debit" | "credit" | "all";
export type CategoryState =
  | "all"
  | "categorized"
  | "uncategorized"
  | "suggested"
  | "assignable"
  | "needs_review"
  | "rejected";
export type TransactionTypeState =
  | "all"
  | "confirmed"
  | "provisional"
  | "needs_review"
  | "suggested";

export interface OverviewStats {
  period_from: string | null;
  period_to: string | null;
  total_income: number;
  gross_expenses: number;
  total_refunds: number;
  total_expenses: number;
  total_debt_payments: number;
  total_asset_allocations: number;
  net_cashflow: number;
  savings_rate: number;
  tx_count: number;
  base_currency: string;
  provisional_transaction_count: number;
  unconverted_count: number;
}

export interface CashflowPoint {
  month: string;
  income: number;
  expenses: number;
  refunds: number;
  debt_payments: number;
  asset_allocations: number;
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
  merchant_display?: string | null;
  merchant_canonical_key?: string | null;
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
  merchant_raw?: string | null;
  merchant_display?: string | null;
  merchant_canonical_key?: string | null;
  merchant_alias_key?: string | null;
  title: string;
  amount: number | string;
  currency: string;
  amount_base?: number | string | null;
  base_currency?: string | null;
  fx_rate?: number | string | null;
  fx_rate_date?: string | null;
  fx_rate_source?: string | null;
  direction: "debit" | "credit";
  category: string | null;
  subcategory: string | null;
  category_source: string | null;
  category_confirmation_method?: string | null;
  category_confirmed_at?: string | null;
  category_origin_ref?: string | null;
  category_predicted: string | null;
  category_confidence: number | null;
  category_predicted_source: string | null;
  category_predicted_ref?: string | null;
  category_suggestion_rejected: boolean;
  raw_transaction_type?: string | null;
  transaction_type: string | null;
  transaction_type_source?: string | null;
  transaction_type_confirmation_method?: string | null;
  transaction_type_confirmed_at?: string | null;
  transaction_type_origin_ref?: string | null;
  transaction_type_predicted?: string | null;
  transaction_type_confidence?: number | null;
  transaction_type_predicted_source?: string | null;
  transaction_type_predicted_ref?: string | null;
  transaction_type_effective?: string | null;
  transaction_type_is_provisional?: boolean;
  transaction_type_needs_review?: boolean;
  source: string;
  is_transfer?: boolean;
  notes?: string | null;
  tags?: string[];
  import_id?: number | null;
  classification_decision?: ClassificationDecision | null;
}

export interface FxRate {
  id: number;
  currency: string;
  base_currency: string;
  rate_date: string;
  rate: number | string;
  source: string;
  created_at: string | null;
}

export interface CurrencyStatus {
  base_currency: string;
  currencies: {
    currency: string;
    count: number;
    total_income: number | string;
    total_expenses: number | string;
    net: number | string;
  }[];
  missing_rates: {
    currency: string;
    base_currency: string;
    rate_date: string;
    count: number;
  }[];
  missing_rate_count: number;
}

export type ClassificationDecisionAction =
  | "accept"
  | "review"
  | "manual"
  | "not_applicable";

export interface ClassificationDecision {
  action: ClassificationDecisionAction;
  reason_code: string;
  threshold_used: number;
  review_floor: number;
  category: string | null;
  confidence: number | null;
  category_candidate: boolean;
}

export interface FilterSummary {
  count: number;
  total_income: number;
  total_expenses: number;
  net: number;
  unconverted_count: number;
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
  merchant_display: string;
  merchant_canonical_key: string;
  count: number;
  total_debit: number | string;
  total_credit: number | string;
  common_category: string | null;
  sample_merchants: string[];
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
  recurring_unruled: {
    merchant: string;
    merchant_display: string;
    merchant_canonical_key: string;
    count: number;
  }[];
  feedback_quality: Record<string, unknown>;
  confusion_hotspots: Record<string, unknown>[];
  anomaly_feedback: Record<string, unknown>;
  subscription_feedback: Record<string, unknown>;
  transaction_type_quality: {
    total: number;
    confirmed: number;
    provisional: number;
    needs_review: number;
    suggested: number;
    rejected: number;
    confirmed_share: number | null;
    class_counts: Record<string, number>;
    source_counts: Record<string, number>;
    suggestion_source_counts: Record<string, number>;
    corrections: {
      source: string;
      suggested_or_previous: string;
      final: string;
      count: number;
    }[];
    unsupported_classes: string[];
  };
  confidence_threshold: number;
  rare_class_threshold: number;
}

export interface ReviewQueueItem {
  transaction_id: number;
  booking_date: string;
  merchant: string;
  merchant_display: string;
  merchant_canonical_key: string;
  title: string;
  amount: number;
  currency: string;
  direction: "debit" | "credit";
  predicted_category: string | null;
  confidence: number | null;
  decision_action: ClassificationDecisionAction;
  decision_reason: string;
  priority_score: number;
  priority_components: Record<string, number>;
  reason_codes: string[];
}

export interface Recap {
  period: "week" | "month" | "custom";
  base_currency: string;
  current_from: string;
  current_to: string;
  previous_from: string;
  previous_to: string;
  cashflow: {
    income: number;
    gross_expenses: number;
    refunds: number;
    expenses: number;
    debt_payments: number;
    asset_allocations: number;
    net: number;
    income_delta: number;
    gross_expenses_delta: number;
    refunds_delta: number;
    expenses_delta: number;
    debt_payments_delta: number;
    asset_allocations_delta: number;
    net_delta: number;
  };
  category_changes: {
    category: string;
    current: number;
    previous: number;
    delta: number;
    current_count: number;
    previous_count: number;
    change_percent: number | null;
  }[];
  merchant_changes: {
    merchant: string;
    merchant_display?: string | null;
    merchant_canonical_key?: string | null;
    current: number;
    previous: number;
    delta: number;
    current_count: number;
    previous_count: number;
    change_percent: number | null;
  }[];
  unconverted_count: number;
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
  base_currency: string;
  model: string;
  horizon: number;
  mape: number | null;
  rmse: number | null;
  validation_folds: number;
  baseline_rmse: number | null;
  improvement_vs_baseline: number | null;
  is_baseline: boolean;
  history_months: number;
  active_months: number;
  required_history_months: number;
  history: ForecastPoint[];
  forecast: ForecastPoint[];
}

export interface Anomaly {
  id: number;
  booking_date: string;
  merchant: string;
  merchant_display: string;
  merchant_canonical_key: string;
  title: string;
  amount: number;
  base_currency: string;
  direction: "debit" | "credit";
  category: string | null;
  severity: number | null;
  priority_score: number | null;
  anomaly_type: string | null;
  reasons: string[];
  reason_codes: string[];
  merchant_occurrences: number;
  merchant_median_amount: number;
  is_recurring_merchant: boolean;
  review_status: "relevant" | "not_relevant" | null;
  reviewed_at: string | null;
  currently_detected: boolean;
}

export interface AnomalyListResponse {
  items: Anomaly[];
  total: number;
  pending_total: number;
  reviewed_total: number;
}

export interface Subscription {
  merchant: string;
  merchant_key: string;
  merchant_display: string;
  merchant_canonical_key: string;
  display_name: string;
  currency: string;
  base_currency: string;
  cadence: string;
  median_amount: number;
  occurrences: number;
  last_seen: string;
  next_expected_date: string | null;
  estimated_monthly_cost_original: number;
  estimated_monthly_cost: number;
  confidence: number;
  status:
    | "active"
    | "new"
    | "price_increased"
    | "price_decreased"
    | "probably_cancelled"
    | "paused_or_missing"
    | "annual_renewal"
    | "needs_review"
    | "ignored";
  source: "detected" | "category" | "confirmed" | "preference";
  previous_amount: number | null;
  current_amount: number | null;
  price_change_pct: number | null;
  price_change_annual_impact: number | null;
  evidence: {
    source?: string;
    occurrences?: number;
    cadence?: string;
    confidence?: number;
    amount_stability?: number | null;
    recent_dates?: string[];
    manual_category_count?: number;
  };
  is_confirmed: boolean;
  is_ignored?: boolean;
  user_decision: "suggested" | "confirmed" | "rejected";
  transactions: SubscriptionTransaction[];
}

export interface SubscriptionTransaction {
  id: number;
  booking_date: string;
  merchant: string;
  merchant_display: string;
  merchant_canonical_key: string;
  title: string;
  amount: number;
  currency: string;
  amount_base: number;
  base_currency: string;
  category: string | null;
  category_source: string | null;
}

export interface SubscriptionUpcomingPayment {
  subscription_key: string;
  display_name: string;
  due_date: string;
  amount: number;
  currency: string;
  amount_base: number;
  base_currency: string;
  status: Subscription["status"];
}

export interface SubscriptionOverview {
  monthly_total: number;
  yearly_total: number;
  next_30_days_count: number;
  next_30_days_total: number;
  base_currency: string;
  upcoming: SubscriptionUpcomingPayment[];
}

export interface SubscriptionPreferenceInput {
  subscription_key: string;
  action: "confirm" | "reject" | "restore" | "update";
  display_name?: string | null;
  cadence_override?: "weekly" | "biweekly" | "monthly" | "yearly" | "unknown" | null;
}

export type FixedChargeCadence =
  | "monthly"
  | "quarterly"
  | "semiannual"
  | "yearly";

export interface FixedCharge {
  id: number;
  name: string;
  amount: number;
  currency: "PLN";
  cadence: FixedChargeCadence;
  anchor_date: string;
  category: string | null;
  active: boolean;
  next_due_date: string | null;
  current_due_date: string | null;
  payment_status: "pending" | "paid" | "overdue" | "paused";
  current_paid_amount: number;
  linked_transaction_count: number;
  last_payment_date: string | null;
  monthly_equivalent: number;
  yearly_cost: number;
}

export interface FixedChargeSummary {
  active_count: number;
  monthly_total: number;
  yearly_total: number;
  next_30_days_count: number;
  next_30_days_total: number;
  base_currency: "PLN";
}

export interface FixedChargeListResponse {
  items: FixedCharge[];
  summary: FixedChargeSummary;
}

export interface FixedChargeCreateInput {
  name: string;
  amount: number;
  cadence: FixedChargeCadence;
  anchor_date: string;
  category?: string | null;
}

export type FixedChargeUpdateInput = Partial<FixedChargeCreateInput> & {
  active?: boolean;
};

export interface FixedChargeTransaction {
  transaction_id: number;
  scheduled_due_date: string | null;
  booking_date: string;
  merchant: string;
  title: string;
  amount: number;
  currency: string;
  amount_base: number;
  base_currency: "PLN";
}

export interface FixedChargeTransactionsResponse {
  fixed_charge_id: number;
  current_due_date: string;
  linked: FixedChargeTransaction[];
  candidates: FixedChargeTransaction[];
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
  node_type?:
    | "income"
    | "category"
    | "merchant"
    | "other"
    | "savings"
    | string
    | null;
  category?: string | null;
  merchant_display?: string | null;
  merchant_canonical_key?: string | null;
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
  quality_report: ImportQualityReport;
  supported_extensions: string[];
}

export interface ImportQualityIssue {
  code: string;
  severity: "error" | "warning";
  count: number;
  sample_rows: number[];
}

export interface ImportQualityReport {
  total_rows: number;
  valid_rows: number;
  blocking_issues: number;
  warnings: number;
  issues: ImportQualityIssue[];
}

export interface ImportSummary {
  import_id: number;
  source: string;
  inserted: number;
  duplicates: number;
  total_rows: number;
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

export interface MerchantAlias {
  id: number;
  alias_key: string;
  alias_label: string;
  canonical_key: string;
  canonical_label: string;
  usage_count: number;
  created_at: string | null;
}

export interface MerchantAliasInput {
  canonical_label: string;
  canonical_key?: string | null;
  aliases: string[];
}

export interface MerchantAliasGroupLabelInput {
  canonical_key: string;
  canonical_label: string;
}

export interface MerchantAliasSuggestion {
  alias_key: string;
  alias_label: string;
  canonical_key: string;
  canonical_label: string;
  count: number;
  total_amount: number | string;
  base_currency: string;
}

export interface MerchantCandidateVariant {
  alias_key: string;
  alias_label: string;
  count: number;
  total_debit: number | string;
  base_currency: string;
}

export interface MerchantCandidate {
  canonical_key: string;
  canonical_label: string;
  suggested_label: string;
  aliases: string[];
  variants: MerchantCandidateVariant[];
  count: number;
  total_debit: number | string;
  base_currency: string;
}

export interface MerchantAliasGroup {
  canonical_key: string;
  canonical_label: string;
  aliases: MerchantAlias[];
}

export interface MlMetricSummary {
  model: string | null;
  macro_f1: number | null;
  weighted_f1: number | null;
  coverage_at_055: number | null;
  accuracy_at_055: number | null;
}

export interface MlModelComparison {
  model_id: string;
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
  model_id: string | null;
  estimator: string | null;
  feature_set: string | null;
  reason_code: string;
  action_codes: string[];
  warning_codes: string[];
  macro_f1: number | null;
  weighted_f1: number | null;
  coverage_at_055: number | null;
  accuracy_at_055: number | null;
  confidence_threshold: number;
  based_on_report: boolean;
}

export interface MlModelStatus {
  exists: boolean;
  path: string;
  updated_at: string | null;
  model_version_id: string | null;
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
  artifact_metadata: Record<string, unknown>;
  compatibility_warnings: string[];
  retrain_signal: MlRetrainSignal | null;
}

export interface MlRetrainSignal {
  retrain_recommended: boolean;
  reason_codes: string[];
  model_updated_at: string | null;
  labels_used_in_current_model: number | null;
  current_label_count: number | null;
  new_labels_since_training: number;
  new_labels_since_training_ratio: number | null;
  feedback_events_since_model: number;
  rejection_rate: number | null;
  suggestion_feedback_total: number;
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
  calendar_months: number;
  date_span_days: number;
  technical_ready: boolean;
  thesis_data_ready: boolean;
  training_ready: boolean;
  training_preflight_reasons: string[];
  model_min_class_support: number;
  supported_classes: string[];
  unsupported_classes: Record<string, number>;
  split_feasible: boolean;
  split_error: string | null;
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

export interface MlLatestTraining {
  exists: boolean;
  job_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  dataset_fingerprint: string | null;
  evaluation_set_id: string | null;
  report_available: boolean;
  candidate_count: number;
  recommended_model_id: string | null;
  representative_model_id: string | null;
  label_count: number | null;
  supported_classes: string[];
  unsupported_classes: Record<string, number>;
  split_counts: Record<string, number | null>;
  metrics: Record<string, unknown>;
  gates: Record<string, unknown>;
  confidence_policy: Record<string, unknown>;
  failed_variants: Record<string, unknown>[];
}

export interface MlDashboard {
  status: MlModelStatus;
  readiness: MlReadiness;
  latest_report: MlLatestReport;
  latest_training: MlLatestTraining;
  model_comparison: MlModelComparison[];
  recommendation: MlModelRecommendation;
  validation_slices: Record<string, unknown>;
  confidence_policy: Record<string, unknown>;
  feedback_quality: Record<string, unknown>;
  feedback_report: FeedbackReport;
  retrain_signal: MlRetrainSignal;
  confusion_hotspots: Record<string, unknown>[];
}

export interface FeedbackReport {
  quality: Record<string, unknown>;
  feedback_events_since_model: number;
  feedback_events_used_in_training: number | null;
  feedback_events_not_yet_in_model: number | null;
  feedback_coverage: number | null;
  coverage_basis: string;
  labels_used_in_current_model: number | null;
  current_label_count: number | null;
  new_labels_since_training: number | null;
  new_labels_since_training_ratio: number | null;
  top_corrected_merchants: Record<string, unknown>[];
  category_corrections: Record<string, unknown>[];
  rejection_by_category: Record<string, unknown>[];
}

export interface MlComparison {
  models: MlModelComparison[];
  recommendation: MlModelRecommendation;
}

export interface MlRetrainResponse {
  status: string;
  message: string;
  job_id: string | null;
}

export interface MlRetrainStatus {
  job_id: string | null;
  status: "idle" | "running" | "completed" | "aborted" | "failed" | string;
  message: string | null;
  estimator: string | null;
  feature_set: string | null;
  started_at: string | null;
  finished_at: string | null;
  report_path: string | null;
  result: Record<string, unknown>;
  error: string | null;
}

export interface MlModelVersion {
  id: string;
  job_id: string | null;
  estimator: string;
  feature_set: string;
  status: "candidate" | "active" | "archived" | "rejected" | string;
  artifact_sha256: string;
  dataset_fingerprint: string;
  evaluation_set_id: string | null;
  metrics: Record<string, unknown>;
  gates: Record<string, unknown>;
  promotable: boolean;
  created_at: string;
  activated_at: string | null;
}

export interface MlEvaluationSet {
  active: boolean;
  id: string | null;
  status: string | null;
  ontology_version: string | null;
  dataset_fingerprint: string | null;
  created_at: string | null;
  config: Record<string, unknown>;
  time_count: number | null;
  merchant_count: number | null;
  excluded_training_count: number | null;
  data_readiness: {
    ready: boolean;
    total: number;
    category_counts: Record<string, number>;
    calendar_months: number;
    date_span_days: number;
    failures: string[];
  } | null;
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

export interface AppLockStatus {
  enabled: boolean;
  locked: boolean;
  timeout_minutes: number;
}

export interface AppLockSetupInput {
  code: string;
  timeout_minutes: 5 | 15 | 30 | 60;
}

export interface AppLockSettingsInput {
  enabled: boolean;
  current_code: string;
  timeout_minutes: 5 | 15 | 30 | 60;
  new_code?: string | null;
}
