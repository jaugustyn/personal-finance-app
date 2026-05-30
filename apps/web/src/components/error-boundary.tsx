"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { useT } from "@/lib/i18n";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

function DefaultFallback({
  error,
  onReset,
}: {
  error: Error;
  onReset: () => void;
}) {
  const { t } = useT();
  return (
    <div className="mx-auto max-w-xl rounded-lg border border-destructive/40 bg-destructive/5 p-6">
      <h2 className="text-lg font-semibold text-destructive">
        {t("errorBoundary.title")}
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        {error.message || t("errorBoundary.fallback")}
      </p>
      <button
        type="button"
        onClick={onReset}
        className="mt-4 inline-flex items-center rounded-md border bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent"
      >
        {t("common.retry")}
      </button>
    </div>
  );
}

/**
 * Lightweight error boundary for top-level pages.
 *
 * Catches render-time errors in the React tree and shows a recoverable
 * fallback UI instead of a blank screen. Network errors from TanStack Query
 * are surfaced through `useQuery`'s `error` state and should be handled by
 * page components — this boundary is a last-resort net.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary caught", error, info);
  }

  reset = (): void => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <DefaultFallback error={this.state.error} onReset={this.reset} />
        )
      );
    }
    return this.props.children;
  }
}
