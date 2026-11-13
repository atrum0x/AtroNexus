import { Plus } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { listCaptures, listCaptureTargets } from "@/api/generated/endpoints/capture/capture";
import { EditButton, PageHeader, TableSkeleton } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { CapturesTable } from "./captures-table";

export default function CapturePage() {
  return (
    <div className="grid gap-8">
      <PageHeader
        title="Capture pages"
        description="Each one is a link that IFS opens from a custom command. The page reads the user's location, IP address and device, and writes them to IFS."
        action={
          <Button render={<Link href="/capture/new" />} nativeButton={false}>
            <Plus />
            New capture page
          </Button>
        }
      />
      <Suspense fallback={<TableSkeleton />}>
        <TargetsTable />
      </Suspense>

      <div className="grid gap-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Recent captures</h2>
          <Link href="/capture/log" className="text-sm text-muted-foreground hover:text-foreground">
            Full log
          </Link>
        </div>
        <Suspense fallback={<TableSkeleton />}>
          <RecentCaptures />
        </Suspense>
      </div>
    </div>
  );
}

async function TargetsTable() {
  const targets = await listCaptureTargets();

  if (targets.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No capture pages yet. Add an{" "}
          <Link href="/connections" className="underline">
            IFS connection
          </Link>{" "}
          first, then create a capture page that uses it.
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
            <TableHead>Connection</TableHead>
            <TableHead>Endpoint</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-0">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {targets.map((t) => (
            <TableRow key={t.id}>
              <TableCell className="font-medium">
                <Link href={`/capture/${t.id}`} className="hover:underline">
                  {t.name}
                </Link>
              </TableCell>
              <TableCell>{t.connection_name}</TableCell>
              <TableCell className="max-w-80 truncate font-mono text-xs text-muted-foreground">
                {t.http_method} {t.endpoint_path}
              </TableCell>
              <TableCell>
                {t.enabled ? <Badge variant="secondary">On</Badge> : <Badge variant="outline">Off</Badge>}
              </TableCell>
              <TableCell className="text-right">
                <EditButton href={`/capture/${t.id}`} label={`Edit ${t.name}`} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

async function RecentCaptures() {
  const captures = await listCaptures({ limit: 10 });
  return <CapturesTable captures={captures} />;
}
