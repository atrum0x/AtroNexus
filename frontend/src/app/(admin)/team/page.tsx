import { Suspense } from "react";

import { listInvitations, listMembers } from "@/api/generated/endpoints/team/team";
import type { MemberOut, UserOut } from "@/api/generated/models";
import { ConfirmButton } from "@/components/confirm-button";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getCurrentUser } from "@/lib/auth";
import { ROLE_DESCRIPTIONS, ROLE_LABELS, canManage } from "@/lib/roles";

import { removeMember, revokeInvitation } from "./actions";
import { InviteForm } from "./invite-form";
import { RoleSelect } from "./role-select";

export default function TeamPage() {
  return (
    <div className="grid gap-8">
      <PageHeader
        title="Team"
        description="Everyone in your organization. Owners and admins change settings and invite people; members can only look."
      />
      <Suspense fallback={<TableSkeleton />}>
        <Team />
      </Suspense>
    </div>
  );
}

/** The roles `me` may give `member`, or none when `me` can't change them (mirrors the backend). */
function assignableRoles(me: UserOut, member: MemberOut): string[] {
  if (!canManage(me) || member.is_me) return [];
  if (me.role === "owner") return ["owner", "admin", "member"];
  return member.role === "owner" ? [] : ["admin", "member"];
}

function memberLabel(m: MemberOut): string {
  return m.name ?? m.email ?? m.username ?? "Unnamed";
}

async function Team() {
  const me = await getCurrentUser();
  const manager = canManage(me);
  const [members, invitations] = await Promise.all([
    listMembers(),
    manager ? listInvitations() : Promise.resolve([]),
  ]);

  return (
    <>
      <Card className="py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead className="w-44">Role</TableHead>
              {manager && (
                <TableHead className="w-0">
                  <span className="sr-only">Actions</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((m) => {
              const roles = assignableRoles(me, m);
              return (
                <TableRow key={m.id}>
                  <TableCell className="font-medium">
                    {memberLabel(m)}
                    {m.is_me && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{m.email ?? `${m.username} (username)`}</TableCell>
                  <TableCell>
                    {roles.length > 0 ? (
                      <RoleSelect memberId={m.id} role={m.role} roles={roles} label={memberLabel(m)} />
                    ) : (
                      <Badge variant={m.role === "member" ? "outline" : "secondary"}>{ROLE_LABELS[m.role]}</Badge>
                    )}
                  </TableCell>
                  {manager && (
                    <TableCell className="text-right">
                      {roles.length > 0 && (
                        <ConfirmButton
                          action={removeMember.bind(null, m.id)}
                          label="Remove"
                          title={`Remove ${memberLabel(m)}?`}
                          description="They're signed out and can't sign in again. Their account is deleted; you can invite them again later."
                        />
                      )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {manager && (
        <div className="grid gap-6 lg:grid-cols-[1fr_22rem] lg:items-start">
          <div className="grid gap-3">
            <h2 className="text-lg font-semibold tracking-tight">Pending invitations</h2>
            {invitations.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  No pending invitations.
                </CardContent>
              </Card>
            ) : (
              <Card className="py-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Invited by</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead className="w-0">
                        <span className="sr-only">Actions</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invitations.map((inv) => (
                      <TableRow key={inv.id}>
                        <TableCell className="font-medium">{inv.email}</TableCell>
                        <TableCell>{ROLE_LABELS[inv.role]}</TableCell>
                        <TableCell className="text-muted-foreground">{inv.invited_by ?? "—"}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(inv.expires_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                        </TableCell>
                        <TableCell className="text-right">
                          {(inv.role !== "owner" || me.role === "owner") && (
                            <ConfirmButton
                              action={revokeInvitation.bind(null, inv.id)}
                              label="Cancel"
                              title={`Cancel the invitation to ${inv.email}?`}
                              description="The link in their email stops working."
                            />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Invite someone</CardTitle>
              <CardDescription>They get an email with a link that works for 7 days.</CardDescription>
            </CardHeader>
            <CardContent>
              <InviteForm roles={me.role === "owner" ? ["member", "admin", "owner"] : ["member", "admin"]} />
            </CardContent>
          </Card>
        </div>
      )}

      <dl className="grid gap-1 text-sm text-muted-foreground sm:grid-cols-[auto_1fr] sm:gap-x-4">
        {Object.entries(ROLE_DESCRIPTIONS).map(([role, description]) => (
          <div key={role} className="contents">
            <dt className="font-medium text-foreground">{ROLE_LABELS[role]}</dt>
            <dd>{description}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}
