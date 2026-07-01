export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly code?: string;

  constructor({
    status,
    statusText,
    detail,
    code,
  }: {
    status: number;
    statusText: string;
    detail: unknown;
    code?: string;
  }) {
    super(`API ${status}: ${formatApiDetail(detail) || statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function apiErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

async function apiErrorFromResponse(res: Response): Promise<ApiError> {
  const raw = await res.text().catch(() => "");
  const parsed = parseErrorBody(raw);
  const detail = parsed.detail ?? parsed.body ?? res.statusText;
  return new ApiError({
    status: res.status,
    statusText: res.statusText,
    detail,
    code: parsed.code,
  });
}

function parseErrorBody(raw: string): {
  body?: unknown;
  detail?: unknown;
  code?: string;
} {
  if (!raw) return {};
  try {
    const body = JSON.parse(raw) as unknown;
    if (body && typeof body === "object") {
      const record = body as Record<string, unknown>;
      return {
        body,
        detail: record.detail,
        code: typeof record.code === "string" ? record.code : detailCode(record.detail),
      };
    }
    return { body };
  } catch {
    return { body: raw };
  }
}

function detailCode(detail: unknown): string | undefined {
  if (!detail || typeof detail !== "object") return undefined;
  const code = (detail as Record<string, unknown>).code;
  return typeof code === "string" ? code : undefined;
}

function formatApiDetail(detail: unknown): string {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  if (typeof detail === "number" || typeof detail === "boolean") return String(detail);
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw await apiErrorFromResponse(res);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function requestMultipart<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, { method: "POST", body: formData });
  if (!res.ok) {
    throw await apiErrorFromResponse(res);
  }
  return (await res.json()) as T;
}
