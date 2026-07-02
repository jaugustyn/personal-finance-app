import { request } from "./client";
import { withQuery } from "./query";
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
    request<ReviewQueueItem[]>(withQuery("/ml/review-queue", { limit })),
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
  ) =>
    request<MlRetrainResponse>(
      withQuery("/ml/retrain", {
        estimator: params.estimator,
        feature_set: params.feature_set,
      }),
      { method: "POST" },
    ),
  forecast: (category: string | null, horizon = 3) =>
    request<ForecastResponse>(withQuery("/forecast", { horizon, category })),
  anomalies: (
    params: {
      direction?: Direction;
      contamination?: number;
      limit?: number;
      mode?: "review" | "suspicious" | "all";
      include_model_only?: boolean;
    } = {},
  ) =>
    request<Anomaly[]>(
      withQuery("/anomalies", {
        direction: params.direction === "all" ? "both" : params.direction,
        contamination: params.contamination,
        limit: params.limit,
        mode: params.mode,
        include_model_only: params.include_model_only ? true : undefined,
      }),
    ),
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
  subscriptions: (minConfidence = 0.0, includeRejected = false) =>
    request<Subscription[]>(
      withQuery("/subscriptions", {
        min_confidence: minConfidence,
        include_rejected: includeRejected ? true : undefined,
      }),
    ),
  subscriptionsOverview: () =>
    request<SubscriptionOverview>("/subscriptions/overview"),
  saveSubscriptionPreference: (payload: SubscriptionPreferenceInput) =>
    request<{ id: number; status: string }>("/subscriptions/preference", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recordSubscriptionFeedback: (payload: {
    action: "confirm";
    merchant?: string | null;
    merchant_canonical_key?: string | null;
    subscription_key?: string | null;
  }) =>
    request<{ id: number | null; status: string }>("/subscriptions/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
