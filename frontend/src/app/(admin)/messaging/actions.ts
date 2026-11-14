"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import {
  createMessageScenario,
  createMessageTemplate,
  createMessagingHookKey,
  deleteMessageScenario,
  deleteMessageTemplate,
  refreshMessageTemplate,
  sendTestMessage,
  updateMessageScenario,
  updateMessageTemplate,
  updateMessagingSetup,
} from "@/api/generated/endpoints/messaging/messaging";
import type { SentMessageOut, ScenarioIn, TemplateIn } from "@/api/generated/models";
import { errorMessage, field } from "@/lib/action-result";

export type SetupState = { error?: string; saved?: boolean };

export async function saveMessagingSetup(_prev: SetupState, form: FormData): Promise<SetupState> {
  try {
    await updateMessagingSetup({
      enabled: form.get("enabled") === "on",
      default_country_code: field(form, "default_country_code")?.replace(/^\+/, "") ?? null,
    });
    refresh();
    return { saved: true };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

export async function newMessagingHookKey(): Promise<{ key?: string; error?: string }> {
  try {
    const { hook_key } = await createMessagingHookKey();
    refresh();
    return { key: hook_key };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

/** Creates (id null) or changes a draft template, then opens it. */
export async function saveTemplate(id: number | null, body: TemplateIn): Promise<{ error?: string }> {
  let savedId = id;
  try {
    if (id === null) savedId = (await createMessageTemplate(body)).id;
    else await updateMessageTemplate(id, body);
  } catch (err) {
    return { error: errorMessage(err) };
  }
  redirect(`/messaging/templates/${savedId}`);
}

export async function refreshTemplate(id: number): Promise<{ error?: string }> {
  try {
    await refreshMessageTemplate(id);
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

export async function removeTemplate(id: number): Promise<{ error?: string }> {
  try {
    await deleteMessageTemplate(id);
  } catch (err) {
    return { error: errorMessage(err) };
  }
  redirect("/messaging/templates");
}

export async function saveScenario(id: number | null, body: ScenarioIn): Promise<{ error?: string }> {
  let savedId = id;
  try {
    if (id === null) savedId = (await createMessageScenario(body)).id;
    else await updateMessageScenario(id, body);
  } catch (err) {
    return { error: errorMessage(err) };
  }
  if (id === null) redirect(`/messaging/scenarios/${savedId}?created=1`);
  refresh();
  return {};
}

export async function removeScenario(id: number): Promise<{ error?: string }> {
  try {
    await deleteMessageScenario(id);
  } catch (err) {
    return { error: errorMessage(err) };
  }
  redirect("/messaging/scenarios");
}

export async function testScenario(
  id: number,
  params: Record<string, unknown>,
): Promise<{ message?: SentMessageOut; error?: string }> {
  try {
    const message = await sendTestMessage(id, { params });
    refresh();
    return { message };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
