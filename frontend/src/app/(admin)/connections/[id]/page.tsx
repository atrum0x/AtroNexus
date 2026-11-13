import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getConnection } from "@/api/generated/endpoints/ifs-connections/ifs-connections";
import { CheckButton } from "@/components/check-button";
import { DeleteButton } from "@/components/delete-button";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { checkConnection, removeConnection } from "../actions";
import { ConnectionForm } from "../connection-form";

export default function EditConnectionPage({ params }: PageProps<"/connections/[id]">) {
  return (
    <div className="grid max-w-2xl gap-6">
      <Suspense fallback={<TableSkeleton />}>
        <EditConnection params={params} />
      </Suspense>
    </div>
  );
}

async function EditConnection({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();

  let connection;
  try {
    connection = await getConnection(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <>
      <PageHeader title={connection.name} back={{ href: "/connections", label: "IFS connections" }} />
      <Card>
        <CardContent>
          <ConnectionForm connection={connection} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Test</CardTitle>
          <CardDescription>
            Signs in to IFS with the saved credentials. Nothing is written. Save your changes first.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CheckButton action={checkConnection.bind(null, id)} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Delete connection</CardTitle>
          <CardDescription>Only possible when no capture page uses it.</CardDescription>
        </CardHeader>
        <CardContent>
          <DeleteButton
            action={removeConnection.bind(null, id)}
            title={`Delete ${connection.name}?`}
            description="The saved credentials are removed. This can't be undone."
          />
        </CardContent>
      </Card>
    </>
  );
}
