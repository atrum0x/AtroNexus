import "server-only";

import { headers } from "next/headers";

/**
 * The visitor's browser address, to pass to the API as X-Client-IP (the API
 * trusts it only together with the internal key). The API uses it for the
 * capture log and for rate limits, so every public call should send it.
 *
 * - On Vercel, x-real-ip is set by Vercel itself; a browser can't override it.
 * - Locally there's no x-real-ip, and Next fills x-forwarded-for with the
 *   socket address. Outside Vercel and local dev, a browser could set both,
 *   so another host would need a proxy that overwrites them.
 */
export async function clientIpHeaders(): Promise<Record<string, string>> {
  const h = await headers();
  const ip = h.get("x-real-ip")?.trim() || h.get("x-forwarded-for")?.split(",").at(-1)?.trim();
  return ip ? { "X-Client-IP": ip } : {};
}
