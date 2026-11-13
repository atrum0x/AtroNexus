import { CheckCircle2, Clock, Hourglass, Link2Off, type LucideIcon, XCircle } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getApproval } from "@/api/generated/endpoints/approvals-public/approvals-public";
import type { ApprovalView } from "@/api/generated/models";
import { StatusBlock, type Tone } from "@/components/status-icon";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { clientIpHeaders } from "@/lib/client-ip";

import { ApprovalForm } from "./approval-form";

export const metadata: Metadata = {
  title: "Approval · AtroNexus",
  robots: { index: false, follow: false },
};

export default function ApprovalPage({ params }: PageProps<"/a/[token]">) {
  return (
    <main className="flex min-h-svh flex-1 flex-col items-center justify-center gap-6 bg-muted/40 px-4 pt-10 pb-[max(2.5rem,env(safe-area-inset-bottom))]">
      <div className="flex items-center gap-2 text-sm font-semibold tracking-tight">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-xs text-primary-foreground">
          A
        </div>
        AtroNexus
      </div>
      <Card className="w-full max-w-md">
        <CardContent className="px-6 py-4">
          <Suspense fallback={<div className="h-72 animate-pulse rounded-lg bg-muted" />}>
            <Approval params={params} />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}

function Message({ icon, tone, title, children }: { icon: LucideIcon; tone: Tone; title: string; children: React.ReactNode }) {
  return (
    <div className="py-2">
      <StatusBlock icon={icon} tone={tone} title={title}>
        {children}
      </StatusBlock>
    </div>
  );
}

async function Approval({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  let view: ApprovalView;
  try {
    view = await getApproval(token, { headers: await clientIpHeaders() });
  } catch (err) {
    if (err instanceof ApiError && err.status === 429) {
      return (
        <Message icon={Hourglass} tone="warning" title="Too many attempts">
          Wait a minute, then open the link again.
        </Message>
      );
    }
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
      return (
        <Message icon={Link2Off} tone="neutral" title="This link isn't valid">
          {err.message}
        </Message>
      );
    }
    throw err;
  }

  if (view.decision === "approved" || view.decision === "rejected") {
    const approved = view.decision === "approved";
    return (
      <Message icon={approved ? CheckCircle2 : XCircle} tone={approved ? "success" : "error"} title={approved ? "Already approved" : "Already rejected"}>
        You decided on this already. You can close this page.
      </Message>
    );
  }
  if (view.decision === "closed" || view.link_state === "used") {
    return (
      <Message icon={CheckCircle2} tone="neutral" title="Already handled">
        Someone took care of this, in IFS or from another email. Nothing is needed from you.
      </Message>
    );
  }
  if (view.link_state === "expired") {
    return (
      <Message icon={Clock} tone="warning" title="This link has expired">
        Authorize it in IFS instead.
      </Message>
    );
  }
  if (view.ifs_status === "SIGNED" || view.ifs_status === "REJECTED") {
    return (
      <Message icon={CheckCircle2} tone="neutral" title="Already handled in IFS">
        This step was already {view.ifs_status === "SIGNED" ? "authorized" : "rejected"} in IFS. Nothing is needed from you.
      </Message>
    );
  }
  if (view.ifs_status === "NOT_YET") {
    return (
      <Message icon={Hourglass} tone="warning" title="Not your turn yet">
        An earlier authorization step is still open. Open this link again once it&apos;s done.
      </Message>
    );
  }

  return (
    <div className="grid gap-5 py-2">
      <div className="grid gap-1 text-center">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{view.organization}</p>
        <h1 className="text-xl font-semibold tracking-tight text-balance">
          Purchase requisition {view.requisition_no}, line {view.line_no}
        </h1>
        <p className="text-sm text-muted-foreground">Waiting for your authorization, {view.approver_name}.</p>
      </div>
      {view.message && (
        <Alert>
          <AlertDescription>{view.message}</AlertDescription>
        </Alert>
      )}
      <Summary summary={view.summary as Record<string, unknown>} />
      <ApprovalForm token={token} />
    </div>
  );
}

function money(amount: unknown, currency: unknown): string | null {
  const n = Number(amount);
  if (amount === null || amount === undefined || Number.isNaN(n)) return null;
  return `${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency ?? ""}`.trim();
}

function Summary({ summary }: { summary: Record<string, unknown> }) {
  const s = (key: string) => (summary[key] === null || summary[key] === undefined ? null : String(summary[key]));
  const item = [s("partNo"), s("description")].filter(Boolean).join(" · ");
  const rows: [string, string | null][] = [
    ["Item", item || null],
    ["Quantity", s("quantity") ? `${s("quantity")} ${s("unit") ?? ""}`.trim() : null],
    ["Unit price", money(summary.unitPrice, summary.currency)],
    ["Supplier", s("supplierName") ?? s("supplierId")],
    ["Wanted by", s("wantedReceiptDate")],
    ["Requested by", s("requisitioner")],
    ["Site", s("site")],
    ["Note", s("note")],
  ];
  const total = money(summary.lineTotal, summary.currency);

  return (
    <div className="grid gap-3 rounded-lg border bg-muted/30 p-4 text-sm">
      {total && (
        <div className="flex items-baseline justify-between gap-4 border-b pb-3">
          <span className="text-muted-foreground">Line total</span>
          <span className="text-lg font-semibold tabular-nums">{total}</span>
        </div>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
        {rows
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="text-right break-words">{value}</dd>
            </div>
          ))}
      </dl>
    </div>
  );
}
