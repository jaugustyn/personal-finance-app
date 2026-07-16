// Public frontend API facade. Existing pages import from "@/lib/api"; the
// implementation is split by feature under ./api/*.

import { assetsApi } from "./api/assets";
import { categoriesApi } from "./api/categories";
import { chatApi } from "./api/chat";
import { currenciesApi } from "./api/currencies";
import { importsApi } from "./api/imports";
import { merchantsApi } from "./api/merchants";
import { mlApi } from "./api/ml";
import { profileApi } from "./api/profile";
import { statsApi } from "./api/stats";
import { transactionsApi } from "./api/transactions";

export type * from "./api/types";
export type {
  MerchantGroupSortBy,
  TransactionFilterParams,
  TransactionListParams,
  TransactionSortBy,
  TransactionSortDirection,
} from "./api/transactions";
export { ApiError, apiErrorMessage, isApiError } from "./api/client";

export const api = {
  ...statsApi,
  ...transactionsApi,
  ...categoriesApi,
  ...currenciesApi,
  ...importsApi,
  ...merchantsApi,
  ...mlApi,
  ...assetsApi,
  ...profileApi,
  ...chatApi,
};
