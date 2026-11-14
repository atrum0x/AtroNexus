"use server";

import {
  decideApproval,
  getApprovalRejectReasons,
} from "@/api/generated/endpoints/approvals-public/approvals-public";
import type { RejectReason } from "@/api/generated/models";
import { errorMessage } from "@/lib/action-result";
import { clientIpHeaders } from "@/lib/client-ip";

export type DecisionResult = { ok: true; result: string; message: string } | { ok: false; message: string };

export async function sendDecision(
  token: string,
  decision: "approve" | "reject",
  reasonId?: string,
  note?: string,
): Promise<DecisionResult> {
  try {
    const res = await decideApproval(
      token,
      { decision, reason_id: reasonId ?? null, note: note?.trim() || null },
      { headers: await clientIpHeaders() },
    );
    return { ok: true, result: res.result, message: res.message };
  } catch (err) {
    return { ok: false, message: errorMessage(err) };
  }
}

export async function loadRejectReasons(token: string): Promise<{ reasons?: RejectReason[]; error?: string }> {
  try {
    return { reasons: await getApprovalRejectReasons(token, { headers: await clientIpHeaders() }) };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
