import { CheckCircle2 } from "lucide-react";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import {
  getMessageScenario,
  listMessages,
  listMessageTemplates,
} from "@/api/generated/endpoints/messaging/messaging";
import { DeleteButton } from "@/components/delete-button";
import { MembersCantChange } from "@/components/manage-only";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";
import { canManage } from "@/lib/roles";

import { removeScenario } from "../../actions";
import { MessagesTable } from "../../messages-table";
import { ScenarioForm } from "../scenario-form";
import { TestSend } from "../test-send";

export default function ScenarioPage({ params, searchParams }: PageProps<"/messaging/scenarios/[id]">) {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <Scenario params={params} searchParams={searchParams} />
    </Suspense>
  );
}

async function Scenario({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();
  const justCreated = (await searchParams).created === "1";
  let data;
  try {
    data = await Promise.all([
      getMessageScenario(id),
      listMessageTemplates(),
      listMessages({ limit: 200 }),
      getCurrentUser(),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  const [scenario, templates, messages, user] = data;
  const manager = canManage(user);
  const mine = messages.filter((m) => m.scenario_code === scenario.code).slice(0, 20);

  return (
    <div className="grid gap-8">
      <PageHeader
        title={<span className="font-mono">{scenario.code}</span>}
        description={scenario.name}
        back={{ href: "/messaging/scenarios", label: "Scenarios" }}
      />
      {justCreated && (
        <Alert className="max-w-3xl">
          <CheckCircle2 />
          <AlertTitle>Scenario created</AlertTitle>
          <AlertDescription>Send a test below, then call it from IFS with the PL/SQL shown.</AlertDescription>
        </Alert>
      )}

      <ScenarioForm scenario={scenario} templates={templates} readOnly={!manager} />
      {!manager && <MembersCantChange what="change, test or delete scenarios" />}

      {manager && (
        <Card className="max-w-3xl">
          <CardHeader>
            <CardTitle>Send a test</CardTitle>
            <CardDescription>
              Sends this scenario once with the values you type, exactly as IFS would. It&apos;s a real WhatsApp
              message to a real number, and it counts. The person must have agreed to get your messages.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TestSend scenarioId={scenario.id} fields={scenario.fields} />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3">
        <h2 className="text-lg font-semibold tracking-tight">Messages from this scenario</h2>
        <MessagesTable messages={mine} />
      </div>

      {manager && (
        <Card className="max-w-3xl">
          <CardHeader>
            <CardTitle>Delete scenario</CardTitle>
            <CardDescription>IFS calls with this code fail afterwards. Its messages stay in the log.</CardDescription>
          </CardHeader>
          <CardContent>
            <DeleteButton
              action={removeScenario.bind(null, scenario.id)}
              title={`Delete ${scenario.code}?`}
              description="IFS calls with this code will be refused. This can't be undone."
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
