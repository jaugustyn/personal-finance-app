import { NextRequest, NextResponse } from "next/server";
import {
  basicAuthFailure,
  validateBasicAuthorization,
} from "@/lib/server/basic-auth";
import {
  hasTrustedHost,
  untrustedHostResponse,
} from "@/lib/server/request-security";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const AUTH_USER = process.env.API_USERNAME ?? process.env.AUTH_USERNAME ?? "";
const AUTH_PASS = process.env.API_PASSWORD ?? process.env.AUTH_PASSWORD ?? "";
const REQUEST_TIMEOUT_MS = 30_000;
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function buildAuthHeader(): string | null {
  if (!AUTH_USER || !AUTH_PASS) return null;
  const token = Buffer.from(`${AUTH_USER}:${AUTH_PASS}`).toString("base64");
  return `Basic ${token}`;
}

function hasSameOrigin(req: NextRequest): boolean {
  const source = req.headers.get("origin") ?? req.headers.get("referer");
  const host = req.headers.get("host");
  if (!source || !host) return false;
  try {
    const protocol = req.nextUrl.protocol.replace(":", "");
    const targetOrigin = new URL(`${protocol}://${host}`).origin;
    return new URL(source).origin === targetOrigin;
  } catch {
    return false;
  }
}

function requestGuard(req: NextRequest): Response | null {
  if (!hasTrustedHost(req)) return untrustedHostResponse();
  const authState = validateBasicAuthorization(req.headers.get("authorization"));
  if (authState !== "disabled" && authState !== "valid") {
    return basicAuthFailure(authState);
  }
  if (!SAFE_METHODS.has(req.method) && !hasSameOrigin(req)) {
    return NextResponse.json(
      {
        detail: {
          code: "cross_site_request_blocked",
          message: "Żądanie modyfikujące dane musi pochodzić z tej aplikacji.",
        },
      },
      { status: 403, headers: { "cache-control": "no-store" } },
    );
  }
  return null;
}

async function forward(req: NextRequest, path: string[]): Promise<Response> {
  const rejected = requestGuard(req);
  if (rejected) return rejected;

  const search = req.nextUrl.search;
  const target = `${API_URL}/${path.join("/")}${search}`;
  const headers: HeadersInit = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  const cookie = req.headers.get("cookie");
  if (cookie) headers["cookie"] = cookie;
  const auth = buildAuthHeader();
  if (auth) headers["authorization"] = auth;

  const init: RequestInit = {
    method: req.method,
    headers,
    cache: "no-store",
  };
  if (!["GET", "HEAD"].includes(req.method)) {
    // Use arrayBuffer() so multipart/form-data uploads (binary file bytes)
    // are forwarded intact. ``req.text()`` would corrupt non-UTF-8 bytes.
    init.body = await req.arrayBuffer();
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const upstream = await fetch(target, { ...init, signal: controller.signal });
    const body = await upstream.arrayBuffer();
    const respHeaders = new Headers();
    respHeaders.set("cache-control", "no-store");
    const upstreamCt = upstream.headers.get("content-type");
    if (upstreamCt) respHeaders.set("content-type", upstreamCt);
    const upstreamCd = upstream.headers.get("content-disposition");
    if (upstreamCd) respHeaders.set("content-disposition", upstreamCd);
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) respHeaders.set("retry-after", retryAfter);
    const authenticate = upstream.headers.get("www-authenticate");
    if (authenticate) respHeaders.set("www-authenticate", authenticate);
    const requestId = upstream.headers.get("x-request-id");
    if (requestId) respHeaders.set("x-request-id", requestId);
    const setCookie = upstream.headers.get("set-cookie");
    if (setCookie) respHeaders.set("set-cookie", setCookie);
    if (upstream.status === 204 || upstream.status === 304) {
      return new NextResponse(null, {
        status: upstream.status,
        headers: respHeaders,
      });
    }
    return new NextResponse(body, { status: upstream.status, headers: respHeaders });
  } catch (error) {
    const aborted = error instanceof Error && error.name === "AbortError";
    return NextResponse.json(
      {
        detail: aborted
          ? "FastAPI upstream timed out"
          : "FastAPI upstream is unavailable",
      },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
