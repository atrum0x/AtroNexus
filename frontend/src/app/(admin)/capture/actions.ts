"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import {
  createCaptureTarget,
  deleteCaptureTarget,
  renewCaptureLink,
  testCaptureTarget,
  updateCaptureTarget,
} from "@/api/generated/endpoints/capture/capture";
import type { CaptureTargetIn, CheckResult } from "@/api/generated/models";
import { errorMessage, field } from "@/lib/action-result";

export type TargetFormState = {
  error?: string;
  values?: Partial<CaptureTargetIn>;
};

function readForm(form: FormData): CaptureTargetIn {
  return {
    name: field(form, "name") ?? "",
    connection_id: Number(field(form, "connection_id") ?? 0),
    endpoint_path: field(form, "endpoint_path") ?? "",
    http_method: field(form, "http_method") === "POST" ? "POST" : "PATCH",
    body_template: (form.get("body_template") as string | null) ?? "",
    enabled: form.get("enabled") === "on",
  };
}

export async function saveTarget(
  id: number | null,
  _prev: TargetFormState,
  form: FormData,
): Promise<TargetFormState> {
  const body = readForm(form);
  let savedId = id;
  try {
    if (id === null) savedId = (await createCaptureTarget(body)).id;
    else await updateCaptureTarget(id, body);
  } catch (err) {
    return { error: errorMessage(err), values: body };
  }
  // After creating, land on the edit page, which shows the link for IFS.
  redirect(id === null ? `/capture/${savedId}?created=1` : "/capture");
}

export async function checkTarget(id: number): Promise<CheckResult> {
  try {
    return await testCaptureTarget(id);
  } catch (err) {
    return { ok: false, message: errorMessage(err) };
  }
}

export async function removeTarget(id: number): Promise<{ error?: string }> {
  try {
    await deleteCaptureTarget(id);
  } catch (err) {
    return { error: errorMessage(err) };
  }
  redirect("/capture");
}

export async function renewLink(id: number): Promise<{ error?: string }> {
  try {
    await renewCaptureLink(id);
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
