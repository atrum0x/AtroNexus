"use server";

import { refresh } from "next/cache";

import { setOrganizationStatus } from "@/api/generated/endpoints/platform/platform";
import { errorMessage, field } from "@/lib/action-result";

export type StatusState = { error?: string };

/** The new status comes from the form, so it always matches the button the admin clicked. */
export async function changeStatus(orgId: number, _prev: StatusState, form: FormData): Promise<StatusState> {
  const status = field(form, "status") === "active" ? "active" : "suspended";
  try {
    await setOrganizationStatus(orgId, { status, reason: field(form, "reason") ?? null });
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
