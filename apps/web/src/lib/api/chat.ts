import { request } from "./client";
import type { ChatRequest, ChatResponse } from "./types";

export const chatApi = {
  chat: (payload: ChatRequest) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
