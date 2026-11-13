import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// Server components can't delete cookies, so when the API rejects a token
// they redirect here. Without this, the stale cookie would make the proxy
// bounce /login back to / in a loop.
export function GET(req: NextRequest) {
  const res = NextResponse.redirect(new URL("/login", req.nextUrl));
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
