"use server";

import { redirect } from "next/navigation";

import {
  createConnection,
  deleteConnection,
  testConnection,
  updateConnection,
} from "@/api/generated/endpoints/ifs-connections/ifs-connections";
import type { CheckResult, IfsConnectionIn } from "@/api/generated/models";
import { errorMessage, field } from "@/lib/action-result";

export type ConnectionFormState = {
  error?: string;
  values?: Partial<IfsConnectionIn>;
};

function readForm(form: FormData): IfsConnectionIn {
  const authType = field(form, "auth_type") === "basic" ? "basic" : "oauth2";
  return {
    name: field(form, "name") ?? "",
    base_url: field(form, "base_url") ?? "",
    auth_type: authType,
    token_url: authType === "oauth2" ? (field(form, "token_url") ?? null) : null,
    client_id: authType === "oauth2" ? (field(form, "client_id") ?? null) : null,
    username: authType === "basic" ? (field(form, "username") ?? null) : null,
    // Not trimmed: a secret may legitimately start or end with a space.
    secret: (form.get("secret") as string | null) || null,
  };
}

export async function saveConnection(
  id: number | null,
  _prev: ConnectionFormState,
  form: FormData,
): Promise<ConnectionFormState> {
  const body = readForm(form);
  // Never send the secret back to the browser, even on error.
  const values = { ...body, secret: undefined };
  try {
    if (id === null) await createConnection(body);
    else await updateConnection(id, body);
  } catch (err) {
    return { error: errorMessage(err), values };
  }
  redirect("/connections");
}

export async function checkConnection(id: number): Promise<CheckResult> {
  try {
    return await testConnection(id);
  } catch (err) {
    return { ok: false, message: errorMessage(err) };
  }
}

export async function removeConnection(id: number): Promise<{ error?: string }> {
  try {
    await deleteConnection(id);
  } catch (err) {
    return { error: errorMessage(err) };
  }
  redirect("/connections");
}
