import { request } from "./client";
import type {
  PersonalRule,
  PersonalRuleInput,
  UserProfile,
  UserProfileInput,
} from "./types";

export const profileApi = {
  profile: () => request<UserProfile>("/profile"),
  patchProfile: (payload: UserProfileInput) =>
    request<UserProfile>("/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  personalRules: () => request<PersonalRule[]>("/profile/rules"),
  createPersonalRule: (payload: PersonalRuleInput) =>
    request<PersonalRule>("/profile/rules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patchPersonalRule: (id: number, payload: Partial<PersonalRuleInput>) =>
    request<PersonalRule>(`/profile/rules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deletePersonalRule: (id: number) =>
    request<void>(`/profile/rules/${id}`, { method: "DELETE" }),
};

