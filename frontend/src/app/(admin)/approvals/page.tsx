import { Suspense } from "react";

import { getApprovalSetup, listApprovalRequests } from "@/api/generated/endpoints/approvals/approvals";
import { listConnections } from "@/api/generated/endpoints/ifs-connections/ifs-connections";
import type { RequestOut } from "@/api/generated/models";
import { CheckButton } from "@/components/check-button";
import { CopyField } from "@/components/copy-field";
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
import { canManage } from "@/lib/roles";

import { checkPackage } from "./actions";
import { HookKey, SetupForm } from "./setup-form";

export default function ApprovalsPage() {
  return (
    <div className="grid gap-8">
      <PageHeader
        title="Approvals"
        description="Approvers get an email and approve or reject purchase requisition lines without signing in to IFS. IFS records the real approver, with their own limits."
      />
      <Suspense fallback={<TableSkeleton />}>
        <Setup />
      </Suspense>
      <div className="grid gap-3">
        <h2 className="text-lg font-semibold tracking-tight">Requests</h2>
        <Suspense fallback={<TableSkeleton />}>
          <RequestLog />
        </Suspense>
      </div>
    </div>
  );
}

async function Setup() {
  const [setup, connections, user] = await Promise.all([getApprovalSetup(), listConnections(), getCurrentUser()]);
  const readOnly = !canManage(user);

  return (
    <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
      <Card>
        <CardHeader>
          <CardTitle>1. Install the IFS package</CardTitle>
          <CardDescription>
            Once per IFS environment. AtroNexus provides the package; its README has every step.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid list-decimal gap-1.5 pl-5 text-sm text-muted-foreground">
            <li>Build and deploy CAtxApprovalUtil and CAtxApprovalHandling (component PURCH).</li>
            <li>
              Add the object property <code className="font-mono text-xs">CAtxApproval / * / HMAC_SECRET</code>{" "}
              with a random value of 32+ characters. AtroNexus never needs it.
            </li>
            <li>Import the event action and enable the event PUR_REQ_LINE_TO_BE_AUTHORIZED.</li>
            <li>Import the routing rule and address C_ATX_APPROVAL_ADDR.</li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Point IFS at AtroNexus</CardTitle>
          <CardDescription>In the routing address C_ATX_APPROVAL_ADDR: this URL, and the key as the bearer token.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">URL</span>
            <CopyField value={setup.hook_url} label="hook URL" />
          </div>
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Hook key</span>
            <HookKey hasKey={setup.has_hook_key} hint={setup.hook_key_hint ?? null} readOnly={readOnly} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Settings</CardTitle>
          <CardDescription>Which IFS connection approves, and how long links work.</CardDescription>
        </CardHeader>
        <CardContent>
          <SetupForm setup={setup} connections={connections} readOnly={readOnly} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>4. Check</CardTitle>
          <CardDescription>
            Checks that IFS has the package and the service user may use it. Then release a test requisition line
            that needs authorization: the approver gets an email within a minute or two.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {readOnly ? (
            <p className="text-sm text-muted-foreground">Only owners and admins can run the check.</p>
          ) : (
            <CheckButton action={checkPackage} label="Check IFS" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const STATUS: Record<string, { label: string; variant: "secondary" | "outline" | "destructive" | "default" }> = {
  sent: { label: "Waiting", variant: "outline" },
  approved: { label: "Approved", variant: "secondary" },
  rejected: { label: "Rejected", variant: "destructive" },
  closed: { label: "Handled elsewhere", variant: "outline" },
};

function when(value?: string | null): string {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "—";
}

async function RequestLog() {
  const rows: RequestOut[] = await listApprovalRequests({ limit: 100 });
  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No approval requests yet. They appear here when IFS sends them.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="py-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Requisition</TableHead>
            <TableHead>Item</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead>Approver</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Opened</TableHead>
            <TableHead>Decided</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const status = STATUS[r.status] ?? { label: r.status, variant: "outline" as const };
            return (
              <TableRow key={r.id}>
                <TableCell className="font-mono text-xs">
                  {r.requisition_no} · {r.line_no} · {r.release_no}
                </TableCell>
                <TableCell className="max-w-48 truncate">{r.item ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{r.line_total ?? "—"}</TableCell>
                <TableCell>
                  <div className="grid">
                    <span>{r.approver_name}</span>
                    <span className="text-xs text-muted-foreground">{r.approver_email}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="grid gap-1">
                    <Badge variant={status.variant}>{status.label}</Badge>
                    {r.error && <span className="max-w-56 text-xs text-destructive">{r.error}</span>}
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{when(r.opened_at)}</TableCell>
                <TableCell className="text-muted-foreground">{when(r.decided_at)}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
