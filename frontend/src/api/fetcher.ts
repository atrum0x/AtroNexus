import "server-only";

import { redirect } from "next/navigation";

import { getSessionToken } from "@/lib/session";

// Mutator for the Orval-generated client in src/api/generated. Every
// generated function goes through here. It runs on the server only because
// the JWT lives in an HttpOnly cookie that the browser can't read.

const API_URL = normalizeBaseUrl(process.env.API_URL ?? "http://localhost:8000");

// Forgives the two easy mistakes when setting API_URL by hand: a missing
// scheme ("api.example.com") and a trailing slash, which would turn every
// request into "//api/...".
function normalizeBaseUrl(raw: string): string {
  let url = raw.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
  return url;
}
// Shared secret with the backend; it refuses requests without it when set.
// Server-only: never prefix it with NEXT_PUBLIC_.
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Endpoints that never take the session token. A 401 from them is a normal
// error (e.g. wrong password), not an expired session.
const NO_TOKEN_PREFIXES = [
  "/api/auth/login",
  "/api/auth/signup",
  "/api/auth/verify-email",
  "/api/auth/forgot-password",
  "/api/auth/reset-password",
  "/api/public/",
];

export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const sendsToken = !NO_TOKEN_PREFIXES.some((p) => url.startsWith(p));
  const token = sendsToken ? await getSessionToken() : undefined;
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (INTERNAL_API_KEY) {
    headers.set("X-Internal-Key", INTERNAL_API_KEY);
  }

  const res = await fetch(`${API_URL}${url}`, { ...init, headers, cache: "no-store" });

  if (res.status === 401 && token) {
    // The token expired or was revoked. Clear the cookie and go to sign-in.
    // (redirect() throws, so callers never see this response.)
    redirect("/session-expired");
  }
  if (!res.ok) {
    throw new ApiError(res.status, await errorMessage(res));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    // FastAPI sends {"detail": "..."} for HTTPException and
    // {"detail": [{msg, ...}]} for validation errors.
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {
    // Not JSON; fall back to the status text.
  }
  return res.statusText || `Request failed with status ${res.status}`;
}
