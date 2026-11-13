import { AlertTriangle } from "lucide-react";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getOrganization } from "@/api/generated/endpoints/platform/platform";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { ROLE_LABELS } from "@/lib/roles";

import { day, dayTime, usd } from "../format";
import { StatusButton } from "./status-button";

export default function PlatformOrganizationPage({ params }: PageProps<"/platform/[id]">) {
  return (
    <div className="grid gap-6">
      <Suspense fallback={<TableSkeleton />}>
        <Organization params={params} />
      </Suspense>
    </div>
  );
}

async function Organization({ params }: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  if (!user.is_platform_admin) notFound();
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();

  let org;
  try {
    org = await getOrganization(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  const suspended = org.status !== "active";

  return (
    <>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            {org.name}
            {suspended ? <Badge variant="destructive">Suspended</Badge> : <Badge variant="secondary">Active</Badge>}
            {org.is_platform_org && <Badge variant="outline">Your organization</Badge>}
          </span>
        }
        description={`Joined ${day(org.created_at)} · ${org.connections} IFS connection${org.connections === 1 ? "" : "s"} · ${org.capture_pages} capture page${org.capture_pages === 1 ? "" : "s"} · ${usd(org.estimated_revenue)} estimated this month`}
        back={{ href: "/platform", label: "Platform" }}
        action={!org.is_platform_org && <StatusButton orgId={org.id} name={org.name} suspended={suspended} />}
      />

      {suspended && (
        <Alert variant="destructive" className="max-w-2xl">
          <AlertTriangle />
          <AlertTitle>Suspended{org.status_changed_at && ` on ${dayTime(org.status_changed_at)}`}</AlertTitle>
          <AlertDescription>{org.status_reason ?? "No reason given."}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <Card className="py-0">
          <CardHeader className="pt-6">
            <CardTitle>Members</CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Email</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {org.members.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="font-medium">
                    {m.name ?? m.username ?? m.email}
                    {m.is_platform_admin && <span className="ml-2 text-xs text-muted-foreground">(platform admin)</span>}
                  </TableCell>
                  <TableCell>{ROLE_LABELS[m.role] ?? m.role}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {m.email ?? "—"}
                    {m.email && !m.email_verified && (
                      <Badge variant="outline" className="ml-2">
                        Unconfirmed
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>

        <Card className="py-0">
          <CardHeader className="pt-6">
            <CardTitle>Tools</CardTitle>
            <CardDescription>Usage is for this month; failures are never billable.</CardDescription>
          </CardHeader>
          {org.tools.length === 0 ? (
            <CardContent className="pb-6 text-sm text-muted-foreground">No tools switched on yet.</CardContent>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tool</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">Sent</TableHead>
                  <TableHead className="text-right">Failed</TableHead>
                  <TableHead className="text-right">Last month</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {org.tools.map((t) => (
                  <TableRow key={t.tool}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell>
                      {t.enabled ? (
                        <span>On{t.enabled_at && <span className="text-muted-foreground"> since {day(t.enabled_at)}</span>}</span>
                      ) : (
                        <span className="text-muted-foreground">Off</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{t.succeeded}</TableCell>
                    <TableCell className="text-right tabular-nums">{t.failed}</TableCell>
                    <TableCell className="text-right tabular-nums">{t.last_month_succeeded}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <Card>
          <CardHeader>
            <CardTitle>Tool history</CardTitle>
            <CardDescription>Every time a tool was switched on or off. Billing will be based on this.</CardDescription>
          </CardHeader>
          <CardContent>
            {org.tool_history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No changes yet.</p>
            ) : (
              <ul className="grid gap-2 text-sm">
                {org.tool_history.map((h, i) => (
                  <li key={i} className="flex justify-between gap-4">
                    <span>
                      {h.name} switched <strong className="font-medium">{h.enabled ? "on" : "off"}</strong>
                      <span className="text-muted-foreground"> by {h.by ?? "the system"}</span>
                    </span>
                    <span className="shrink-0 text-muted-foreground">{dayTime(h.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent errors</CardTitle>
          </CardHeader>
          <CardContent>
            {org.recent_errors.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing has failed.</p>
            ) : (
              <ul className="grid gap-3 text-sm">
                {org.recent_errors.map((e, i) => (
                  <li key={i} className="grid gap-0.5">
                    <span className="font-medium">{e.title}</span>
                    <span className="text-muted-foreground">{e.message}</span>
                    <span className="text-xs text-muted-foreground">{dayTime(e.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
