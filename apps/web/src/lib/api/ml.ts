import { request } from "./client";
import type { Anomaly, Direction, ForecastResponse, Subscription } from "./types";

export const mlApi = {
  forecast: (category: string | null, horizon = 3) => {
    const q = new URLSearchParams({ horizon: String(horizon) });
    if (category) q.set("category", category);
    return request<ForecastResponse>(`/forecast?${q.toString()}`);
  },
  anomalies: (params: { direction?: Direction; contamination?: number; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.direction) q.set("direction", params.direction === "all" ? "both" : params.direction);
    if (params.contamination) q.set("contamination", String(params.contamination));
    if (params.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<Anomaly[]>(`/anomalies${qs ? `?${qs}` : ""}`);
  },
  subscriptions: (minConfidence = 0.0) =>
    request<Subscription[]>(`/subscriptions?min_confidence=${minConfidence}`),
};
