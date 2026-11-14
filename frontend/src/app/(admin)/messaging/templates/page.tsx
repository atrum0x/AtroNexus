import { Plus } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { listMessageTemplates } from "@/api/generated/endpoints/messaging/messaging";
import { ManageOnly } from "@/components/manage-only";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { TemplateStatus } from "./status-badge";

export default function TemplatesPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Templates"
        description="The text of each WhatsApp message. WhatsApp reviews every template before it can be sent, usually within minutes."
        action={
          <Suspense>
            <ManageOnly>
              <Button render={<Link href="/messaging/templates/new" />} nativeButton={false}>
                <Plus />
                New template
              </Button>
            </ManageOnly>
          </Suspense>
        }
      />
      <Suspense fallback={<TableSkeleton />}>
        <TemplateList />
      </Suspense>
    </div>
  );
}

async function TemplateList() {
  const templates = await listMessageTemplates();
  if (templates.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No templates yet. Create one, then use it in a scenario.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="py-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Message</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Scenarios</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {templates.map((t) => (
            <TableRow key={t.id}>
              <TableCell>
                <Link href={`/messaging/templates/${t.id}`} className="font-medium underline-offset-4 hover:underline">
                  {t.name}
                </Link>
                <span className="ml-1.5 text-xs text-muted-foreground">{t.language}</span>
              </TableCell>
              <TableCell>
                <p className="line-clamp-1 max-w-96 text-sm text-muted-foreground">{t.body_text}</p>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">{t.category.toLowerCase()}</TableCell>
              <TableCell>
                <TemplateStatus status={t.status} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{t.used_by}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
