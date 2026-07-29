import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  basicAuthFailure,
  validateBasicAuthorization,
} from "@/lib/server/basic-auth";
import {
  hasTrustedHost,
  untrustedHostResponse,
} from "@/lib/server/request-security";

export function proxy(request: NextRequest): Response {
  if (!hasTrustedHost(request)) return untrustedHostResponse();
  const state = validateBasicAuthorization(request.headers.get("authorization"));
  if (state !== "disabled" && state !== "valid") {
    return basicAuthFailure(state);
  }
  const response = NextResponse.next();
  response.headers.set("cache-control", "no-store");
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)",
  ],
};
