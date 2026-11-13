import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// Optimistic check only: it looks for the cookie but doesn't verify the JWT.
// The real check happens when server code calls the API with the token
// (see the mutator in api/fetcher.ts).

// Signed-out only: signed-in users get sent home.
const SIGNED_OUT_ONLY = ["/login", "/signup", "/forgot-password"];
// Open to everyone, signed in or not.
// - /c/: capture links, opened by IFS users who don't have an AtroNexus account.
// - /verify-email, /reset-password: links from emails, which may be opened in
//   a browser that is (or isn't) signed in.
const OPEN_PREFIXES = ["/c/", "/verify-email", "/reset-password"];

export function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname;
  if (OPEN_PREFIXES.some((p) => path.startsWith(p))) {
    return NextResponse.next();
  }

  const hasSession = req.cookies.has(SESSION_COOKIE);
  const signedOutPage = SIGNED_OUT_ONLY.includes(path);
  if (!hasSession && !signedOutPage) {
    return NextResponse.redirect(new URL("/login", req.nextUrl));
  }
  if (hasSession && signedOutPage) {
    return NextResponse.redirect(new URL("/", req.nextUrl));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|svg|jpg|ico)$).*)"],
};
