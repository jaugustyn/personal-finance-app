import type { NextRequest } from "next/server";

const DEFAULT_TRUSTED_HOSTS = "localhost,127.0.0.1,[::1]";

function trustedHosts(): Set<string> {
  const configured = process.env.WEB_TRUSTED_HOSTS ?? DEFAULT_TRUSTED_HOSTS;
  return new Set(
    configured
      .split(",")
      .map((host) => host.trim().toLowerCase())
      .filter((host) => host && host !== "*"),
  );
}

function hostnameFromHeader(host: string): string | null {
  try {
    return new URL(`http://${host}`).hostname.toLowerCase();
  } catch {
    return null;
  }
}

export function hasTrustedHost(request: NextRequest): boolean {
  const rawHost = request.headers.get("host");
  if (!rawHost) return false;
  const hostname = hostnameFromHeader(rawHost);
  return hostname !== null && trustedHosts().has(hostname);
}

export function untrustedHostResponse(): Response {
  return new Response("Nieprawidłowy host żądania.", {
    status: 400,
    headers: {
      "cache-control": "no-store",
      "content-type": "text/plain; charset=utf-8",
    },
  });
}
