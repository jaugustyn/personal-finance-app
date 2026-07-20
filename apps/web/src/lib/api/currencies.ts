import { request } from "./client";
import type { CurrencyStatus, FxRate } from "./types";

export interface FxRateInput {
  currency: string;
  rate_date: string;
  rate: number;
}

export const currenciesApi = {
  currencyStatus: () => request<CurrencyStatus>("/currencies/status"),
  fxRates: () => request<FxRate[]>("/currencies/rates"),
  addFxRate: (payload: FxRateInput) =>
    request<FxRate>("/currencies/rates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  fetchNbpRates: () =>
    request<{ fetched: number; missing: number }>("/currencies/fetch-nbp", {
      method: "POST",
    }),
  recomputeCurrencies: () =>
    request<{ updated: number; missing: number }>("/currencies/recompute", {
      method: "POST",
    }),
};
