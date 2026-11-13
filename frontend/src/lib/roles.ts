import type { UserOut } from "@/api/generated/models";

// Mirrors the backend: owners and admins change settings, members only look.
// The backend enforces it; this only hides controls that would be refused.

export const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};

export const ROLE_DESCRIPTIONS: Record<string, string> = {
  owner: "Everything, including managing owners",
  admin: "Manage connections, capture pages and the team",
  member: "View everything, change nothing",
};

export function canManage(user: Pick<UserOut, "role">): boolean {
  return user.role === "owner" || user.role === "admin";
}
