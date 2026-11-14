import { Download } from "lucide-react";
import { Suspense } from "react";

import {
  getApprovalSetup,
  listApprovalFlows,
  listApprovalRequests,
} from "@/api/generated/endpoints/approvals/approvals";
import { listConnections } from "@/api/generated/endpoints/ifs-connections/ifs-connections";
import type { FlowOut, RequestOut } from "@/api/generated/models";
import { CheckButton } from "@/components/check-button";
import { CopyField } from "@/components/copy-field";
import { HookKey } from "@/components/hook-key";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

import { checkPackage, newHookKey } from "./actions";
import { FlowSwitch } from "./flow-switch";
import { SetupForm } from "./setup-form";

export default function ApprovalsPage() {
  return (
    <div className="grid gap-8">
      <PageHeader
        title="Approvals"
        description="Approvers get an email and approve or reject without signing in to IFS. IFS records the real approver, with their own limits."
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
  const [setup, flows, connections, user] = await Promise.all([
    getApprovalSetup(),
    listApprovalFlows(),
    listConnections(),
    getCurrentUser(),
  ]);
  const readOnly = !canManage(user);
  const chosen = flows.filter((f) => f.enabled);
  const events = chosen.flatMap((f) => f.ifs_events);

  return (
    <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>1. Choose approval types</CardTitle>
          <CardDescription>
            Which IFS approvals go out by email. The IFS package you download has the event actions for the
            types switched on here; switch on another one later and download it again.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FlowList flows={flows} readOnly={readOnly} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Install the IFS package</CardTitle>
          <CardDescription>
            Once per IFS environment. The download has the code to build, the configuration package ready to
            import, and a README with every step.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid justify-items-start gap-1.5">
            {chosen.length > 0 ? (
              /* A plain link: it's a file download from a route handler, not a page. */
              <Button variant="outline" render={<a href="/api/approvals/package" download />} nativeButton={false}>
                <Download />
                Download IFS package
              </Button>
            ) : (
              <>
                <Button variant="outline" disabled>
                  <Download />
                  Download IFS package
                </Button>
                <span className="text-xs text-muted-foreground">Switch on an approval type first.</span>
              </>
            )}
          </div>
          <ol className="grid list-decimal gap-1.5 pl-5 text-sm text-muted-foreground">
            <li>Build and deploy CAtxApprovalUtil and CAtxApprovalHandling (component PURCH).</li>
            <li>
              Add the object property <code className="font-mono text-xs">CAtxApproval / * / HMAC_SECRET</code>{" "}
              with a random value of 32+ characters. AtroNexus never needs it.
            </li>
            <li>
              Import <code className="font-mono text-xs">config/C_ATX_APPROVALS.zip</code>
              {events.length > 0 && (
                <>
                  {" "}and enable the event{events.length > 1 ? "s" : ""}{" "}
                  {events.map((e, i) => (
                    <span key={e}>
                      {i > 0 && ", "}
                      <code className="font-mono text-xs">{e}</code>
                    </span>
                  ))}
                </>
              )}
              .
            </li>
            <li>Import the routing rule and address from config/connect; the address already points here.</li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Point IFS at AtroNexus</CardTitle>
          <CardDescription>In the routing address C_ATX_APPROVAL_ADDR: this URL, and the key as the bearer token.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">URL</span>
            <CopyField value={setup.hook_url} label="hook URL" />
          </div>
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Hook key</span>
            <HookKey
              hasKey={setup.has_hook_key}
              hint={setup.hook_key_hint ?? null}
              readOnly={readOnly}
              addressName="C_ATX_APPROVAL_ADDR"
              create={newHookKey}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>4. Settings</CardTitle>
          <CardDescription>Which IFS connection approves, and how long links work.</CardDescription>
        </CardHeader>
        <CardContent>
          <SetupForm setup={setup} connections={connections} readOnly={readOnly} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>5. Check</CardTitle>
          <CardDescription>
            Checks that IFS has the package and the service user may use it. Then send something that needs
            authorization (for example, release a test requisition line): the approver gets an email within a
            minute or two.
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

function FlowList({ flows, readOnly }: { flows: FlowOut[]; readOnly: boolean }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {flows.map((f) => (
        <li
          key={f.code}
          className={`flex items-start justify-between gap-4 rounded-lg border p-3 ${f.available ? "" : "bg-muted/40"}`}
        >
          <div className="grid gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-sm font-medium ${f.available ? "" : "text-muted-foreground"}`}>{f.name}</span>
              {!f.available && <Badge variant="outline">Coming soon</Badge>}
            </div>
            <span className="text-xs text-muted-foreground">{f.description}</span>
          </div>
          {f.available &&
            (readOnly ? (
              <Badge variant={f.enabled ? "secondary" : "outline"}>{f.enabled ? "On" : "Off"}</Badge>
            ) : (
              <FlowSwitch code={f.code} name={f.name} enabled={f.enabled} />
            ))}
        </li>
      ))}
    </ul>
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
            <TableHead>Approval</TableHead>
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
                <TableCell>
                  <div className="grid">
                    <span className="font-mono text-xs">{r.reference}</span>
                    <span className="text-xs text-muted-foreground">{r.kind_name}</span>
                  </div>
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
