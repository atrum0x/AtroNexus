import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// Optimistic check only: it looks for the cookie but doesn't verify the JWT.
// The real check happens when server code calls the API with the token
// (see the mutator in api/fetcher.ts).

// Signed-out only: signed-in users get sent home.
const LOGIN = "/login";
// Open to everyone, signed in or not. Capture links (/c/...) are opened by
// IFS users who don't have an AtroNexus account.
const OPEN_PREFIXES = ["/c/"];

export function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname;
  if (OPEN_PREFIXES.some((p) => path.startsWith(p))) {
    return NextResponse.next();
  }

  const hasSession = req.cookies.has(SESSION_COOKIE);
  if (!hasSession && path !== LOGIN) {
    return NextResponse.redirect(new URL(LOGIN, req.nextUrl));
  }
  if (hasSession && path === LOGIN) {
    return NextResponse.redirect(new URL("/", req.nextUrl));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|svg|jpg|ico)$).*)"],
};
