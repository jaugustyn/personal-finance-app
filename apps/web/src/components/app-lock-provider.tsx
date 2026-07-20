"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, LockKeyhole, RefreshCw } from "lucide-react";
import { api, isApiError, type AppLockStatus } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const LOCK_EVENT = "finance:app-locked";
const CHANNEL_NAME = "finance-app-lock";
const STORAGE_KEY = "finance-app-lock-event";
const HEARTBEAT_INTERVAL_MS = 30_000;

type LockMessage = "activity" | "locked" | "unlocked";

interface AppLockContextValue {
  status: AppLockStatus;
  applyStatus: (status: AppLockStatus, broadcast?: boolean) => void;
  lock: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AppLockContext = React.createContext<AppLockContextValue | null>(null);

export function useAppLock(): AppLockContextValue {
  const context = React.useContext(AppLockContext);
  if (!context) {
    throw new Error("useAppLock must be used within AppLockProvider");
  }
  return context;
}

export function AppLockProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = React.useState<AppLockStatus | null>(null);
  const [statusError, setStatusError] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const channelRef = React.useRef<BroadcastChannel | null>(null);
  const lastActivityRef = React.useRef(0);
  const lastHeartbeatRef = React.useRef(0);

  const broadcast = React.useCallback((type: LockMessage) => {
    if (channelRef.current) {
      channelRef.current.postMessage({ type });
      return;
    }
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ type, at: Date.now(), nonce: crypto.randomUUID() }),
      );
    } catch {
      // Cross-tab synchronization is a convenience; server state stays authoritative.
    }
  }, []);

  const applyStatus = React.useCallback(
    (next: AppLockStatus, notify = false) => {
      setStatus(next);
      setStatusError(false);
      setLoading(false);
      if (next.locked) queryClient.clear();
      if (notify) broadcast(next.locked ? "locked" : "unlocked");
    },
    [broadcast, queryClient],
  );

  const refresh = React.useCallback(async () => {
    try {
      const next = await api.appLockStatus();
      applyStatus(next);
    } catch {
      queryClient.clear();
      setStatus(null);
      setStatusError(true);
      setLoading(false);
    }
  }, [applyStatus, queryClient]);

  const lockLocally = React.useCallback(
    (notify: boolean) => {
      setStatus((current) =>
        current?.enabled ? { ...current, locked: true } : current,
      );
      queryClient.clear();
      if (notify) broadcast("locked");
    },
    [broadcast, queryClient],
  );

  const lock = React.useCallback(async () => {
    lockLocally(true);
    try {
      await api.lockApp();
    } catch {
      // Fail closed. The retry on the lock screen will resolve current server state.
    }
  }, [lockLocally]);

  React.useEffect(() => {
    let active = true;
    void api.appLockStatus().then(
      (next) => {
        if (active) applyStatus(next);
      },
      () => {
        if (!active) return;
        queryClient.clear();
        setStatus(null);
        setStatusError(true);
        setLoading(false);
      },
    );
    return () => {
      active = false;
    };
  }, [applyStatus, queryClient]);

  React.useEffect(() => {
    if (typeof BroadcastChannel !== "undefined") {
      channelRef.current = new BroadcastChannel(CHANNEL_NAME);
    }

    const handleMessage = (type: LockMessage) => {
      if (type === "activity") {
        lastActivityRef.current = Date.now();
      } else if (type === "locked") {
        lockLocally(false);
      } else {
        void refresh();
      }
    };
    const channel = channelRef.current;
    if (channel) {
      channel.onmessage = (event: MessageEvent<{ type?: LockMessage }>) => {
        if (event.data.type) handleMessage(event.data.type);
      };
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY || !event.newValue) return;
      try {
        const message = JSON.parse(event.newValue) as { type?: LockMessage };
        if (message.type) handleMessage(message.type);
      } catch {
        // Ignore malformed local storage values.
      }
    };
    const onLocked = () => lockLocally(true);
    window.addEventListener("storage", onStorage);
    window.addEventListener(LOCK_EVENT, onLocked);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(LOCK_EVENT, onLocked);
      channel?.close();
      channelRef.current = null;
    };
  }, [lockLocally, refresh]);

  React.useEffect(() => {
    if (!status?.enabled || status.locked) return;

    const registerActivity = () => {
      const now = Date.now();
      lastActivityRef.current = now;
      if (now - lastHeartbeatRef.current < HEARTBEAT_INTERVAL_MS) return;
      lastHeartbeatRef.current = now;
      broadcast("activity");
      void api.registerAppActivity().catch((error) => {
        if (!isApiError(error) || error.status !== 423) {
          queryClient.clear();
          setStatus(null);
          setStatusError(true);
        }
      });
    };
    const activityEvents: (keyof WindowEventMap)[] = [
      "keydown",
      "pointerdown",
      "pointermove",
      "touchstart",
      "scroll",
    ];
    for (const event of activityEvents) {
      window.addEventListener(event, registerActivity, { passive: true });
    }

    const timer = window.setInterval(() => {
      const timeoutMs = status.timeout_minutes * 60_000;
      if (Date.now() - lastActivityRef.current >= timeoutMs) void refresh();
    }, 5_000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      for (const event of activityEvents) {
        window.removeEventListener(event, registerActivity);
      }
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [broadcast, queryClient, refresh, status]);

  if (loading) return <AppLockLoading />;
  if (statusError || !status) return <AppLockStatusError onRetry={refresh} />;
  if (status.enabled && status.locked) {
    return (
      <AppUnlockScreen
        onUnlocked={(next) => {
          lastActivityRef.current = Date.now();
          applyStatus(next, true);
        }}
      />
    );
  }

  return (
    <AppLockContext.Provider value={{ status, applyStatus, lock, refresh }}>
      {children}
    </AppLockContext.Provider>
  );
}

function AppUnlockScreen({
  onUnlocked,
}: {
  onUnlocked: (status: AppLockStatus) => void;
}) {
  const { t } = useT();
  const [code, setCode] = React.useState("");
  const [error, setError] = React.useState("");
  const [pending, setPending] = React.useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const submittedCode = String(
      new FormData(event.currentTarget).get("code") ?? "",
    );
    setError("");
    setPending(true);
    try {
      onUnlocked(await api.unlockApp(submittedCode));
    } catch (caught) {
      if (isApiError(caught) && caught.status === 429) {
        setError(
          t("appLock.tooManyAttempts", {
            seconds: caught.retryAfter ?? 300,
          }),
        );
      } else if (isApiError(caught) && caught.status === 401) {
        setError(t("appLock.invalidCode"));
      } else {
        setError(t("appLock.unlockUnavailable"));
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-5 rounded-xl border bg-card p-6 shadow-lg"
      >
        <div className="space-y-2 text-center">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-primary">
            <LockKeyhole className="h-5 w-5" />
          </div>
          <h1 className="text-xl font-semibold">{t("app.title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("appLock.locked")}
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="app-lock-code">{t("appLock.code")}</Label>
          <Input
            id="app-lock-code"
            name="code"
            type="password"
            autoFocus
            autoComplete="current-password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            minLength={6}
            maxLength={128}
            required
          />
          {error && (
            <p className="text-sm text-destructive" role="alert" aria-live="polite">
              {error}
            </p>
          )}
        </div>
        <Button type="submit" className="w-full" disabled={pending}>
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}
          {t("appLock.unlock")}
        </Button>
      </form>
    </main>
  );
}

function AppLockLoading() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </main>
  );
}

function AppLockStatusError({ onRetry }: { onRetry: () => Promise<void> }) {
  const { t } = useT();
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="max-w-sm space-y-4 text-center">
        <LockKeyhole className="mx-auto h-7 w-7 text-muted-foreground" />
        <div>
          <h1 className="font-semibold">{t("appLock.statusUnavailable")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("appLock.statusUnavailableHelp")}
          </p>
        </div>
        <Button variant="outline" onClick={() => void onRetry()}>
          <RefreshCw className="h-4 w-4" />
          {t("common.retry")}
        </Button>
      </div>
    </main>
  );
}
