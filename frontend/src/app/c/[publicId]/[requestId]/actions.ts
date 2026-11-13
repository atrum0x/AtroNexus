"use server";

import { headers } from "next/headers";

import { ApiError } from "@/api/fetcher";
import { submitCapture } from "@/api/generated/endpoints/capture-public/capture-public";
import type { CaptureResult, CaptureSubmit } from "@/api/generated/models";
import { errorMessage } from "@/lib/action-result";

export type CaptureInput = Omit<CaptureSubmit, "user_agent">;

export async function sendCapture(
  publicId: string,
  requestId: string,
  input: CaptureInput,
): Promise<CaptureResult> {
  const h = await headers();
  // The browser's address, passed on to the API as X-Client-IP (trusted there
  // only together with the internal key).
  // - On Vercel, x-real-ip is set by Vercel itself; a browser can't override it.
  // - Locally there's no x-real-ip, and Next fills x-forwarded-for with the
  //   socket address. Outside Vercel and local dev, a browser could set both,
  //   so another host would need a proxy that overwrites them.
  const clientIp =
    h.get("x-real-ip")?.trim() || h.get("x-forwarded-for")?.split(",").at(-1)?.trim() || undefined;

  try {
    return await submitCapture(
      publicId,
      requestId,
      { ...input, user_agent: h.get("user-agent")?.slice(0, 512) ?? null },
      { headers: clientIp ? { "X-Client-IP": clientIp } : {} },
    );
  } catch (err) {
    // Already captured (e.g. a second tab): nothing left to do.
    if (err instanceof ApiError && err.status === 409) return { ok: true, message: err.message };
    return { ok: false, message: errorMessage(err) };
  }
}
