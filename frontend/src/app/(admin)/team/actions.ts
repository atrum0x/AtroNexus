"use server";

import { refresh } from "next/cache";

import {
  changeMemberRole,
  createInvitation,
  removeMember as removeMemberRequest,
  revokeInvitation as revokeInvitationRequest,
} from "@/api/generated/endpoints/team/team";
import type { InvitationInRole } from "@/api/generated/models";
import { errorMessage, field } from "@/lib/action-result";

const ROLES = ["owner", "admin", "member"] as const;

function asRole(value: string | undefined): InvitationInRole {
  return (ROLES as readonly string[]).includes(value ?? "") ? (value as InvitationInRole) : "member";
}

export type InviteState = { error?: string; sent?: string; email?: string };

export async function inviteMember(_prev: InviteState, form: FormData): Promise<InviteState> {
  const email = field(form, "email");
  if (!email) return { error: "Enter an email address." };
  try {
    const inv = await createInvitation({ email, role: asRole(field(form, "role")) });
    refresh();
    return { sent: `Invitation sent to ${inv.email}.` };
  } catch (err) {
    return { error: errorMessage(err), email };
  }
}

export async function revokeInvitation(id: number): Promise<{ error?: string }> {
  try {
    await revokeInvitationRequest(id);
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

export async function setMemberRole(id: number, role: string): Promise<{ error?: string }> {
  try {
    await changeMemberRole(id, { role: asRole(role) });
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

export async function removeMember(id: number): Promise<{ error?: string }> {
  try {
    await removeMemberRequest(id);
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
