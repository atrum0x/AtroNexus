"use server";

import { refresh } from "next/cache";

import {
  checkApprovalPackage,
  createHookKey,
  updateApprovalFlow,
  updateApprovalSetup,
} from "@/api/generated/endpoints/approvals/approvals";
import type { CheckResult } from "@/api/generated/models";
import { errorMessage, field } from "@/lib/action-result";

export type SetupState = { error?: string; saved?: boolean };

export async function saveSetup(_prev: SetupState, form: FormData): Promise<SetupState> {
  const connection = field(form, "connection_id");
  const days = Number(field(form, "link_days") ?? 7);
  try {
    await updateApprovalSetup({
      connection_id: connection ? Number(connection) : null,
      enabled: form.get("enabled") === "on",
      link_days: Number.isFinite(days) ? days : 7,
    });
    refresh();
    return { saved: true };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

export async function newHookKey(): Promise<{ key?: string; error?: string }> {
  try {
    const { hook_key } = await createHookKey();
    refresh();
    return { key: hook_key };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

export async function checkPackage(): Promise<CheckResult> {
  try {
    return await checkApprovalPackage();
  } catch (err) {
    return { ok: false, message: errorMessage(err) };
  }
}

export async function setFlowEnabled(code: string, enabled: boolean): Promise<{ error?: string }> {
  try {
    await updateApprovalFlow(code, { enabled });
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
