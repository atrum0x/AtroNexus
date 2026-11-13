import Link from "next/link";
import { Suspense } from "react";

import { getCaptureDefaults } from "@/api/generated/endpoints/capture/capture";
import { listConnections } from "@/api/generated/endpoints/ifs-connections/ifs-connections";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";

import { TargetForm } from "../target-form";

export default function NewCaptureTargetPage() {
  return (
    <div className="grid max-w-2xl gap-6">
      <PageHeader
        title="New capture page"
        description="Choose the IFS connection, and where in IFS the result goes."
        back={{ href: "/capture", label: "Capture pages" }}
      />
      <Card>
        <CardContent>
          <Suspense fallback={<TableSkeleton />}>
            <NewTargetForm />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}

async function NewTargetForm() {
  const [connections, defaults] = await Promise.all([listConnections(), getCaptureDefaults()]);
  if (connections.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Add an{" "}
        <Link href="/connections/new" className="underline">
          IFS connection
        </Link>{" "}
        first. A capture
        page needs one to write to IFS.
      </p>
    );
  }
  return <TargetForm connections={connections} defaults={defaults} />;
}
