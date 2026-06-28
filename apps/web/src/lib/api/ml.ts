import { request } from "./client";
import type {
  Anomaly,
  Direction,
  ForecastResponse,
  MlComparison,
  MlDashboard,
  FeedbackReport,
  MlFeedbackInput,
  MlFeedbackResponse,
  MlReclassifyResponse,
  MlRetrainResponse,
  ReviewQueueItem,
  Subscription,
  SubscriptionOverview,
  SubscriptionPreferenceInput,
} from "./types";

export const mlApi = {
  mlDashboard: () => request<MlDashboard>("/ml/dashboard"),
  mlComparison: () => request<MlComparison>("/ml/comparison"),
  reviewQueue: (limit = 20) =>
    request<ReviewQueueItem[]>(`/ml/review-queue?limit=${limit}`),
  feedbackReport: () => request<FeedbackReport>("/ml/feedback-report"),
  recordMlFeedback: (payload: MlFeedbackInput) =>
    request<MlFeedbackResponse>("/ml/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reclassifyTransactions: () =>
    request<MlReclassifyResponse>("/ml/reclassify", { method: "POST" }),
  retrainClassifier: (
    params: { estimator?: string; feature_set?: string } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.estimator) q.set("estimator", params.estimator);
    if (params.feature_set) q.set("feature_set", params.feature_set);
    const qs = q.toString();
    return request<MlRetrainResponse>(
      `/ml/retrain${qs ? `?${qs}` : ""}`,
      { method: "POST" },
    );
  },
  forecast: (category: string | null, horizon = 3) => {
    const q = new URLSearchParams({ horizon: String(horizon) });
    if (category) q.set("category", category);
    return request<ForecastResponse>(`/forecast?${q.toString()}`);
  },
  anomalies: (
    params: {
      direction?: Direction;
      contamination?: number;
      limit?: number;
      mode?: "review" | "suspicious" | "all";
      include_model_only?: boolean;
    } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.direction) q.set("direction", params.direction === "all" ? "both" : params.direction);
    if (params.contamination) q.set("contamination", String(params.contamination));
    if (params.limit) q.set("limit", String(params.limit));
    if (params.mode) q.set("mode", params.mode);
    if (params.include_model_only) q.set("include_model_only", "true");
    const qs = q.toString();
    return request<Anomaly[]>(`/anomalies${qs ? `?${qs}` : ""}`);
  },
  recordAnomalyFeedback: (
    transactionId: number,
    action: "relevant" | "not_relevant" | "ignore_merchant",
  ) =>
    request<{ id: number | null; status: string }>(
      `/anomalies/${transactionId}/feedback`,
      {
        method: "POST",
        body: JSON.stringify({ action }),
      },
    ),
  subscriptions: (minConfidence = 0.0, includeRejected = false) => {
    const q = new URLSearchParams({ min_confidence: String(minConfidence) });
    if (includeRejected) q.set("include_rejected", "true");
    return request<Subscription[]>(`/subscriptions?${q.toString()}`);
  },
  subscriptionsOverview: () =>
    request<SubscriptionOverview>("/subscriptions/overview"),
  saveSubscriptionPreference: (payload: SubscriptionPreferenceInput) =>
    request<{ id: number; status: string }>("/subscriptions/preference", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recordSubscriptionFeedback: (
    merchant: string,
    action: "confirm",
    subscriptionKey?: string,
  ) =>
    request<{ id: number | null; status: string }>("/subscriptions/feedback", {
      method: "POST",
      body: JSON.stringify({ merchant, action, subscription_key: subscriptionKey }),
    }),
};
