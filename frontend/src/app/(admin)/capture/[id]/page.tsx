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
import { ConfirmButton } from "@/components/confirm-button";
import { DeleteButton } from "@/components/delete-button";
import { MembersCantChange } from "@/components/manage-only";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";
import { canManage } from "@/lib/roles";

import { checkTarget, removeTarget, renewLink } from "../actions";
import { CaptureLink } from "../capture-link";
import { CapturesTable } from "../captures-table";
import { TargetForm } from "../target-form";

export default function CaptureTargetPage({
  params,
  searchParams,
}: PageProps<"/capture/[id]">) {
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
      getCurrentUser(),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  const [target, connections, defaults, captures, user] = data;
  const manager = canManage(user);

  return (
    <>
      <PageHeader
        title={target.name}
        back={{ href: "/capture", label: "Capture pages" }}
      />

      {justCreated && (
        <Alert className="max-w-2xl">
          <CheckCircle2 />
          <AlertTitle>Capture page created</AlertTitle>
          <AlertDescription>
            Put the link below in your IFS custom command.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid max-w-2xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Link for IFS</CardTitle>
            <CardDescription>
              Use this as the URL of a custom command on the capture request
              entity. IFS fills in{" "}
              <code className="font-mono text-xs">{"${RequestId}"}</code> from
              the record. The page must be served over HTTPS, or browsers
              won&apos;t share the location.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CaptureLink publicId={target.public_id} />
            {manager && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                <p className="max-w-md text-sm text-muted-foreground">
                  Link leaked or shared by mistake? Give this page a new address. Every old link stops working.
                </p>
                <ConfirmButton
                  action={renewLink.bind(null, id)}
                  tone="neutral"
                  label="New link"
                  title="Give this capture page a new link?"
                  description="Every link with the current address stops working at once, including ones already sent. Then update the URL in your IFS custom command to the new link, or new captures from IFS will fail."
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
          </CardHeader>
          <CardContent>
            <TargetForm
              target={target}
              connections={connections}
              defaults={defaults}
              readOnly={!manager}
            />
            {!manager && (
              <div className="mt-4">
                <MembersCantChange what="change, test or delete capture pages" />
              </div>
            )}
          </CardContent>
        </Card>

        {manager && (
          <Card>
            <CardHeader>
              <CardTitle>Test</CardTitle>
              <CardDescription>
                Signs in to IFS and opens the projection in the endpoint path.
                Nothing is written.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CheckButton
                action={checkTarget.bind(null, id)}
                label="Test IFS access"
              />
            </CardContent>
          </Card>
        )}
      </div>

      <div className="grid gap-3">
        <h2 className="text-lg font-semibold tracking-tight">
          Captures from this page
        </h2>
        <CapturesTable captures={captures} showTarget={false} />
      </div>

      {manager && (
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Delete capture page</CardTitle>
            <CardDescription>
              Only possible before it has any captures. After that, turn it off
              instead.
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
      )}
    </>
  );
}
