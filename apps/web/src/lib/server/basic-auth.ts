import { timingSafeEqual } from "node:crypto";

export type BasicAuthState = "disabled" | "valid" | "invalid" | "misconfigured";

function credentials(): { username: string; password: string } {
  return {
    username: process.env.API_USERNAME ?? process.env.AUTH_USERNAME ?? "",
    password: process.env.API_PASSWORD ?? process.env.AUTH_PASSWORD ?? "",
  };
}

function constantTimeEqual(left: string, right: string): boolean {
  const leftBytes = Buffer.from(left, "utf8");
  const rightBytes = Buffer.from(right, "utf8");
  if (leftBytes.length !== rightBytes.length) return false;
  return timingSafeEqual(leftBytes, rightBytes);
}

export function validateBasicAuthorization(header: string | null): BasicAuthState {
  const { username, password } = credentials();
  if (!username && !password) return "disabled";
  if (!username || !password) return "misconfigured";
  if (!header?.startsWith("Basic ")) return "invalid";

  const provided = header.slice("Basic ".length).trim();
  const expected = Buffer.from(`${username}:${password}`, "utf8").toString("base64");
  return constantTimeEqual(provided, expected) ? "valid" : "invalid";
}

export function basicAuthFailure(state: BasicAuthState): Response {
  const misconfigured = state === "misconfigured";
  const headers = new Headers({
    "cache-control": "no-store",
    "content-type": "text/plain; charset=utf-8",
  });
  if (!misconfigured) {
    headers.set(
      "www-authenticate",
      'Basic realm="Personal Finance", charset="UTF-8"',
    );
  }
  return new Response(
    misconfigured
      ? "Uwierzytelnianie aplikacji jest nieprawidłowo skonfigurowane."
      : "Uwierzytelnienie jest wymagane.",
    { status: misconfigured ? 503 : 401, headers },
  );
}
