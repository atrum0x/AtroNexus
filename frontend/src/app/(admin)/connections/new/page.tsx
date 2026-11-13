import { Suspense } from "react";

import { ManageOnly, MembersCantChange } from "@/components/manage-only";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";

import { ConnectionForm } from "../connection-form";

export default function NewConnectionPage() {
  return (
    <div className="grid max-w-2xl gap-6">
      <PageHeader
        title="New IFS connection"
        description="Use a dedicated IFS service user, with access only to what the tools need."
        back={{ href: "/connections", label: "IFS connections" }}
      />
      <Card>
        <CardContent>
          <Suspense fallback={<TableSkeleton />}>
            <ManageOnly fallback={<MembersCantChange what="add connections" />}>
              <ConnectionForm />
            </ManageOnly>
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
