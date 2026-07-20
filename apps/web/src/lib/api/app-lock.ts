import { request } from "./client";
import type {
  AppLockSettingsInput,
  AppLockSetupInput,
  AppLockStatus,
} from "./types";

export const appLockApi = {
  appLockStatus: () => request<AppLockStatus>("/app-lock/status"),
  setupAppLock: (payload: AppLockSetupInput) =>
    request<AppLockStatus>("/app-lock/setup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  unlockApp: (code: string) =>
    request<AppLockStatus>("/app-lock/unlock", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  registerAppActivity: () =>
    request<void>("/app-lock/activity", { method: "POST" }),
  lockApp: () => request<void>("/app-lock/lock", { method: "POST" }),
  updateAppLock: (payload: AppLockSettingsInput) =>
    request<AppLockStatus>("/app-lock/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};

