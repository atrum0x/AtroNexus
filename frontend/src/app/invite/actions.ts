"use server";

import { redirect } from "next/navigation";

import { acceptInvitation } from "@/api/generated/endpoints/team-public/team-public";
import { errorMessage, field } from "@/lib/action-result";
import { setSession } from "@/lib/session";

export type AcceptState = { error?: string; name?: string };

export async function acceptInvite(token: string, _prev: AcceptState, form: FormData): Promise<AcceptState> {
  const name = field(form, "name");
  const password = String(form.get("password") ?? "");
  if (!name) return { error: "Enter your name." };
  if (password.length < 8) return { error: "Use a password of at least 8 characters.", name };

  try {
    const session = await acceptInvitation(token, { name, password });
    // Replaces any session this browser had (e.g. someone else's account).
    await setSession(session.access_token, session.expires_in);
  } catch (err) {
    return { error: errorMessage(err), name };
  }
  redirect("/");
}
