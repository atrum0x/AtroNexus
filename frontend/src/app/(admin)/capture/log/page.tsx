import { Suspense } from "react";

import { listCaptures } from "@/api/generated/endpoints/capture/capture";
import { PageHeader, TableSkeleton } from "@/components/page-header";

import { CapturesTable } from "../captures-table";

export default function CaptureLogPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Capture log"
        description="The latest 500 captures, and whether IFS accepted them."
        back={{ href: "/capture", label: "Capture pages" }}
      />
      <Suspense fallback={<TableSkeleton />}>
        <Log />
      </Suspense>
    </div>
  );
}

async function Log() {
  const captures = await listCaptures({ limit: 500 });
  return <CapturesTable captures={captures} />;
}
