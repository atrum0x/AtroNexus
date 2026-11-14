import Link from "next/link";
import { Suspense } from "react";

import { listMessageTemplates } from "@/api/generated/endpoints/messaging/messaging";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { ScenarioForm } from "../scenario-form";

export default function NewScenarioPage() {
  return (
    <div className="grid gap-6">
      <PageHeader title="New scenario" back={{ href: "/messaging/scenarios", label: "Scenarios" }} />
      <Suspense fallback={<TableSkeleton />}>
        <NewScenario />
      </Suspense>
    </div>
  );
}

async function NewScenario() {
  const templates = await listMessageTemplates();
  if (templates.length === 0) {
    return (
      <Card className="max-w-xl">
        <CardContent className="grid justify-items-start gap-3">
          <p className="text-sm text-muted-foreground">A scenario sends a template. Create one first.</p>
          <Button render={<Link href="/messaging/templates/new" />} nativeButton={false}>
            New template
          </Button>
        </CardContent>
      </Card>
    );
  }
  return <ScenarioForm templates={templates} />;
}
