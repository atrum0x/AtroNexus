import "server-only";

import { cookies } from "next/headers";

import { SESSION_COOKIE } from "@/lib/session-cookie";

// The FastAPI access token lives in an HttpOnly cookie, so browser JavaScript
// never sees it. Only server code (actions, server components) reads it.

export async function setSession(token: string, maxAgeSeconds: number) {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: maxAgeSeconds,
  });
}

export async function getSessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

export async function clearSession() {
  (await cookies()).delete(SESSION_COOKIE);
}
