"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Loader2, Send, Sparkles, Trash2, User } from "lucide-react";
import { api, type ChatRequest, type ChatResponse } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  tool?: string | null;
  toolArgs?: Record<string, unknown> | null;
  error?: boolean;
}

const SUGGESTION_KEYS = [
  "assistant.suggest.spend",
  "assistant.suggest.topCategory",
  "assistant.suggest.cashflow",
  "assistant.suggest.topMerchants",
  "assistant.suggest.subscriptions",
  "assistant.suggest.savings",
] as const;

export default function AssistantPage() {
  const { t } = useT();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const nextId = useRef(1);
  const scrollRef = useRef<HTMLDivElement>(null);

  const chat = useMutation({
    mutationFn: (payload: ChatRequest) => api.chat(payload),
    onSuccess: (res: ChatResponse) => {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId.current++,
          role: "assistant",
          content: res.answer,
          tool: res.tool,
          toolArgs: res.tool_args,
        },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId.current++,
          role: "assistant",
          content: t("assistant.error"),
          error: true,
        },
      ]);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, chat.isPending]);

  function ask(question: string) {
    const q = question.trim();
    if (!q || chat.isPending) return;
    const previous = [...messages]
      .reverse()
      .find((message) => message.role === "assistant" && message.tool);
    setMessages((prev) => [
      ...prev,
      { id: nextId.current++, role: "user", content: q },
    ]);
    setInput("");
    chat.mutate({
      question: q,
      previous_tool: previous?.tool ?? null,
      previous_tool_args: previous?.toolArgs ?? null,
    });
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    ask(input);
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4">
      <PageHeader
        title={t("assistant.title")}
        description={t("assistant.subtitle")}
        actions={
          messages.length > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessages([])}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t("assistant.clear")}
            </Button>
          ) : undefined
        }
      />

      <Card className="flex min-h-0 flex-1 flex-col">
        <CardContent className="flex min-h-0 flex-1 flex-col gap-4 p-4">
          <div
            ref={scrollRef}
            className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto"
          >
            {isEmpty ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <p className="max-w-md text-sm text-muted-foreground">
                  {t("assistant.empty")}
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTION_KEYS.map((key) => (
                    <Button
                      key={key}
                      variant="outline"
                      size="sm"
                      onClick={() => ask(t(key))}
                    >
                      {t(key)}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => <MessageBubble key={m.id} message={m} />)
            )}

            {chat.isPending && (
              <div className="flex items-center gap-3">
                <Avatar role="assistant" />
                <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("assistant.thinking")}
                </div>
              </div>
            )}
          </div>

          <form onSubmit={onSubmit} className="flex items-center gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("assistant.placeholder")}
              disabled={chat.isPending}
            />
            <Button type="submit" disabled={chat.isPending || !input.trim()}>
              <Send className="h-4 w-4" />
              <span className="sr-only">{t("assistant.send")}</span>
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const { t } = useT();
  const isUser = message.role === "user";
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      <Avatar role={message.role} />
      <div
        className={cn(
          "max-w-[80%] space-y-1.5",
          isUser && "flex flex-col items-end",
        )}
      >
        <span className="text-xs font-medium text-muted-foreground">
          {isUser ? t("assistant.you") : t("assistant.bot")}
        </span>
        <div
          className={cn(
            "whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
            isUser
              ? "bg-primary text-primary-foreground"
              : message.error
                ? "bg-destructive/10 text-destructive"
                : "bg-muted",
          )}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  const isUser = role === "user";
  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
        isUser
          ? "bg-secondary text-secondary-foreground"
          : "bg-primary/10 text-primary",
      )}
    >
      {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
    </div>
  );
}
