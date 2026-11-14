import { ArrowRight, CircleAlert, CircleCheck, Download } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import {
  getMessagingSetup,
  listMessages,
  listMessageScenarios,
  listMessageTemplates,
} from "@/api/generated/endpoints/messaging/messaging";
import { CopyField } from "@/components/copy-field";
import { HookKey } from "@/components/hook-key";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";
import { canManage } from "@/lib/roles";

import { newMessagingHookKey } from "./actions";
import { MessagesTable } from "./messages-table";
import { MessagingSetupForm } from "./setup-form";

export default function MessagingPage() {
  return (
    <div className="grid gap-8">
      <PageHeader
        title="Messaging"
        description="Send WhatsApp messages from anything in IFS. Write a template, map IFS values to it in a scenario, and call the scenario from an event action or workflow."
      />
      <Suspense fallback={<TableSkeleton />}>
        <Setup />
      </Suspense>
      <div className="grid gap-3">
        <h2 className="text-lg font-semibold tracking-tight">Messages</h2>
        <Suspense fallback={<TableSkeleton />}>
          <MessageLog />
        </Suspense>
      </div>
    </div>
  );
}

function Step({ done, children }: { done: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      {done ? (
        <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
      ) : (
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      )}
      <span className={done ? "text-muted-foreground" : ""}>{children}</span>
    </li>
  );
}

async function Setup() {
  const [setup, templates, scenarios, user] = await Promise.all([
    getMessagingSetup(),
    listMessageTemplates(),
    listMessageScenarios(),
    getCurrentUser(),
  ]);
  const readOnly = !canManage(user);
  const approved = templates.filter((t) => t.status === "approved").length;

  return (
    <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
      <Card>
        <CardHeader>
          <CardTitle>WhatsApp sender</CardTitle>
          <CardDescription>
            Messages come from the AtroNexus WhatsApp number for now. Sending from your own company number is coming.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <p className="text-sm">
            {setup.sender.connected ? (
              <>
                Sending from <span className="font-medium">{setup.sender.display_number ?? "the AtroNexus number"}</span>
                .
              </>
            ) : (
              <span className="text-destructive">WhatsApp isn&apos;t connected on this AtroNexus yet.</span>
            )}
          </p>
          <ul className="grid gap-1.5">
            <Step done={approved > 0}>
              <Link href="/messaging/templates" className="underline-offset-4 hover:underline">
                Templates
              </Link>
              : {templates.length} ({approved} approved by WhatsApp)
            </Step>
            <Step done={scenarios.length > 0}>
              <Link href="/messaging/scenarios" className="underline-offset-4 hover:underline">
                Scenarios
              </Link>
              : {scenarios.length}
            </Step>
            <Step done={setup.has_hook_key && setup.enabled}>IFS connected and sending switched on (below)</Step>
          </ul>
          {!readOnly && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" render={<Link href="/messaging/templates/new" />} nativeButton={false}>
                New template
                <ArrowRight />
              </Button>
              <Button variant="outline" size="sm" render={<Link href="/messaging/scenarios/new" />} nativeButton={false}>
                New scenario
                <ArrowRight />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Install the IFS package</CardTitle>
          <CardDescription>
            Once per IFS environment. It adds C_Atx_Message_Util_API.Send, which any event action, workflow or
            PL/SQL can call, and the routing to AtroNexus.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div>
            {/* A plain link: it's a file download from a route handler, not a page. */}
            <Button variant="outline" render={<a href="/api/messaging/package" download />} nativeButton={false}>
              <Download />
              Download IFS package
            </Button>
          </div>
          <ol className="grid list-decimal gap-1.5 pl-5 text-sm text-muted-foreground">
            <li>Build and deploy CAtxMessageUtil (component FNDBAS).</li>
            <li>Import the routing rule and address from config/connect; the address already points here.</li>
            <li>Paste the hook key into the routing address C_ATX_MESSAGE_ADDR.</li>
            <li>
              Call it, e.g. from an event action:{" "}
              <code className="font-mono text-xs break-all">
                C_Atx_Message_Util_API.Send(&apos;ORDER_SHIPPED&apos;, C_Atx_Message_Util_API.Params(&apos;phone&apos;,
                &apos;&amp;PHONE&apos;, ...))
              </code>
            </li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connect IFS</CardTitle>
          <CardDescription>In the routing address C_ATX_MESSAGE_ADDR: this URL, and the key as the bearer token.</CardDescription>
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
              addressName="C_ATX_MESSAGE_ADDR"
              create={newMessagingHookKey}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <MessagingSetupForm setup={setup} readOnly={readOnly} />
        </CardContent>
      </Card>
    </div>
  );
}

async function MessageLog() {
  return <MessagesTable messages={await listMessages({ limit: 100 })} />;
}
