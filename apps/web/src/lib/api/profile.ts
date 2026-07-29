import { request } from "./client";
import type {
  AssistantSettings,
  AssistantSettingsInput,
  PersonalRule,
  PersonalRuleInput,
} from "./types";

export const profileApi = {
  assistantSettings: () => request<AssistantSettings>("/profile/assistant"),
  updateAssistantSettings: (payload: AssistantSettingsInput) =>
    request<AssistantSettings>("/profile/assistant", {
      method: "PUT",
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
