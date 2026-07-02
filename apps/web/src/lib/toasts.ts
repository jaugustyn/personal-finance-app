import { toast } from "sonner";
import { isApiError } from "./api/client";

export function showErrorToast(error: unknown, fallbackTitle: string): void {
  const message = errorToastMessage(error);
  const title = isApiError(error)
    ? `${fallbackTitle} (${error.status})`
    : (message ?? fallbackTitle);

  toast.error(title, {
    description:
      message && message !== title && message !== fallbackTitle
        ? message
        : undefined,
  });
}

function errorToastMessage(error: unknown): string | undefined {
  if (isApiError(error)) {
    return detailMessage(error.detail) ?? error.message;
  }
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return undefined;
}

function detailMessage(detail: unknown): string | undefined {
  if (detail == null) return undefined;
  if (typeof detail === "string") return detail;
  if (typeof detail === "number" || typeof detail === "boolean") {
    return String(detail);
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => detailMessage(item))
      .filter((item): item is string => Boolean(item));
    return messages.length > 0 ? messages.slice(0, 3).join("; ") : undefined;
  }
  if (typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    for (const key of ["message", "error", "msg", "detail"]) {
      const value = detailMessage(record[key]);
      if (value) return value;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return undefined;
    }
  }
  return undefined;
}
