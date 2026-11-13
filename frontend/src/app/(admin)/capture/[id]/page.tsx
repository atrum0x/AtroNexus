import { CheckCircle2 } from "lucide-react";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import {
  getCaptureDefaults,
  getCaptureTarget,
  listCaptures,
} from "@/api/generated/endpoints/capture/capture";
import { listConnections } from "@/api/generated/endpoints/ifs-connections/ifs-connections";
import { CheckButton } from "@/components/check-button";
import { DeleteButton } from "@/components/delete-button";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { checkTarget, removeTarget } from "../actions";
import { CaptureLink } from "../capture-link";
import { CapturesTable } from "../captures-table";
import { TargetForm } from "../target-form";

export default function CaptureTargetPage({ params, searchParams }: PageProps<"/capture/[id]">) {
  return (
    <div className="grid gap-6">
      <Suspense fallback={<TableSkeleton />}>
        <CaptureTarget params={params} searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function CaptureTarget({
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
      getCaptureTarget(id),
      listConnections(),
      getCaptureDefaults(),
      listCaptures({ target_id: id, limit: 20 }),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  const [target, connections, defaults, captures] = data;

  return (
    <>
      <PageHeader title={target.name} back={{ href: "/capture", label: "Capture pages" }} />

      {justCreated && (
        <Alert className="max-w-2xl">
          <CheckCircle2 />
          <AlertTitle>Capture page created</AlertTitle>
          <AlertDescription>Put the link below in your IFS custom command.</AlertDescription>
        </Alert>
      )}

      <div className="grid max-w-2xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Link for IFS</CardTitle>
            <CardDescription>
              Use this as the URL of a custom command on the capture request entity. IFS fills in{" "}
              <code className="font-mono text-xs">{"${RequestId}"}</code> from the record. The page
              must be served over HTTPS, or browsers won&apos;t share the location.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CaptureLink publicId={target.public_id} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
          </CardHeader>
          <CardContent>
            <TargetForm target={target} connections={connections} defaults={defaults} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Test</CardTitle>
            <CardDescription>
              Signs in to IFS and opens the projection in the endpoint path. Nothing is written.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CheckButton action={checkTarget.bind(null, id)} label="Test IFS access" />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3">
        <h2 className="text-lg font-semibold tracking-tight">Captures from this page</h2>
        <CapturesTable captures={captures} showTarget={false} />
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Delete capture page</CardTitle>
          <CardDescription>
            Only possible before it has any captures. After that, turn it off instead.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DeleteButton
            action={removeTarget.bind(null, id)}
            title={`Delete ${target.name}?`}
            description="Links to this page will stop working. This can't be undone."
          />
        </CardContent>
      </Card>
    </>
  );
}
