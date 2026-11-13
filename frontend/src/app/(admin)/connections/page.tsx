import { Plus } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { listConnections } from "@/api/generated/endpoints/ifs-connections/ifs-connections";
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

export default function ConnectionsPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="IFS connections"
        description="The IFS environments the tools write to, and the service user each one signs in as."
        action={
          <Button render={<Link href="/connections/new" />} nativeButton={false}>
            <Plus />
            New connection
          </Button>
        }
      />
      <Suspense fallback={<TableSkeleton />}>
        <ConnectionsTable />
      </Suspense>
    </div>
  );
}

async function ConnectionsTable() {
  const connections = await listConnections();

  if (connections.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No connections yet. Add one with the IFS address and a service user.
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
            <TableHead>IFS base URL</TableHead>
            <TableHead>Signs in with</TableHead>
            <TableHead className="w-0">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {connections.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="font-medium">
                <Link href={`/connections/${c.id}`} className="hover:underline">
                  {c.name}
                </Link>
              </TableCell>
              <TableCell className="text-muted-foreground">{c.base_url}</TableCell>
              <TableCell>
                <Badge variant="secondary">
                  {c.auth_type === "oauth2" ? `OAuth2 · ${c.client_id}` : `Basic · ${c.username}`}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <EditButton href={`/connections/${c.id}`} label={`Edit ${c.name}`} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
