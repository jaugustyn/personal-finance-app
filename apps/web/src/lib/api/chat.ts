import { request } from "./client";
import type { ChatHealthResponse, ChatRequest, ChatResponse } from "./types";

export const chatApi = {
  chat: (payload: ChatRequest) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  chatHealth: () =>
    request<ChatHealthResponse>("/chat/health"),
};
