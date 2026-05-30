// Public frontend API facade. Existing pages import from "@/lib/api"; the
// implementation is split by feature under ./api/*.

import { assetsApi } from "./api/assets";
import { categoriesApi } from "./api/categories";
import { importsApi } from "./api/imports";
import { mlApi } from "./api/ml";
import { profileApi } from "./api/profile";
import { statsApi } from "./api/stats";
import { transactionsApi } from "./api/transactions";

export type * from "./api/types";

export const api = {
  ...statsApi,
  ...transactionsApi,
  ...categoriesApi,
  ...importsApi,
  ...mlApi,
  ...assetsApi,
  ...profileApi,
};
