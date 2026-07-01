export type QueryValue = string | number | boolean | null | undefined;

export function buildQuery(params: Record<string, QueryValue>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }
  return query.toString();
}

export function withQuery(path: string, params: Record<string, QueryValue>): string {
  const query = buildQuery(params);
  return `${path}${query ? `?${query}` : ""}`;
}
