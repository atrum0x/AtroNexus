"use server";

import { headers } from "next/headers";

import { ApiError } from "@/api/fetcher";
import { submitCapture } from "@/api/generated/endpoints/capture-public/capture-public";
import type { CaptureResult, CaptureSubmit } from "@/api/generated/models";
import { errorMessage } from "@/lib/action-result";
import { clientIpHeaders } from "@/lib/client-ip";

export type CaptureInput = Omit<CaptureSubmit, "user_agent">;

export async function sendCapture(
  publicId: string,
  requestId: string,
  input: CaptureInput,
): Promise<CaptureResult> {
  const h = await headers();
  try {
    return await submitCapture(
      publicId,
      requestId,
      { ...input, user_agent: h.get("user-agent")?.slice(0, 512) ?? null },
      { headers: await clientIpHeaders() },
    );
  } catch (err) {
    // Already captured (e.g. a second tab): nothing left to do.
    if (err instanceof ApiError && err.status === 409) return { ok: true, message: err.message };
    return { ok: false, message: errorMessage(err) };
  }
}
