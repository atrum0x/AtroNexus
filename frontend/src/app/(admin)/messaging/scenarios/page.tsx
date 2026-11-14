import { Plus } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { listMessageScenarios } from "@/api/generated/endpoints/messaging/messaging";
import { ManageOnly } from "@/components/manage-only";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { TemplateStatus } from "../templates/status-badge";

export default function ScenariosPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Scenarios"
        description="Each scenario is a code IFS calls, like ORDER_SHIPPED: which template it sends, to whom, and which IFS values fill it."
        action={
          <Suspense>
            <ManageOnly>
              <Button render={<Link href="/messaging/scenarios/new" />} nativeButton={false}>
                <Plus />
                New scenario
              </Button>
            </ManageOnly>
          </Suspense>
        }
      />
      <Suspense fallback={<TableSkeleton />}>
        <ScenarioList />
      </Suspense>
    </div>
  );
}

async function ScenarioList() {
  const scenarios = await listMessageScenarios();
  if (scenarios.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No scenarios yet. Create a template first, then a scenario that uses it.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="py-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Code</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Template</TableHead>
            <TableHead>IFS sends</TableHead>
            <TableHead>State</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {scenarios.map((s) => (
            <TableRow key={s.id}>
              <TableCell>
                <Link
                  href={`/messaging/scenarios/${s.id}`}
                  className="font-mono text-xs font-medium underline-offset-4 hover:underline"
                >
                  {s.code}
                </Link>
              </TableCell>
              <TableCell>{s.name}</TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm">{s.template_name}</span>
                  {s.template_status !== "approved" && <TemplateStatus status={s.template_status} />}
                </div>
              </TableCell>
              <TableCell className="max-w-64 font-mono text-xs text-muted-foreground">{s.fields.join(", ")}</TableCell>
              <TableCell>
                <Badge variant={s.enabled ? "secondary" : "outline"}>{s.enabled ? "On" : "Off"}</Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
