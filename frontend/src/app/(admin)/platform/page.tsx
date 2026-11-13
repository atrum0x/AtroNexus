import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { listOrganizations } from "@/api/generated/endpoints/platform/platform";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getCurrentUser } from "@/lib/auth";
import { getTools } from "@/lib/tools";

import { day, monthName, usd } from "./format";

export default function PlatformPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Platform"
        description="Every customer organization. Only you, as the platform admin, can see this."
      />
      <Suspense fallback={<TableSkeleton />}>
        <Customers />
      </Suspense>
    </div>
  );
}

async function Customers() {
  const user = await getCurrentUser();
  if (!user.is_platform_admin) notFound();
  const [data, tools] = await Promise.all([listOrganizations(), getTools()]);
  const toolNames = Object.fromEntries(tools.map((t) => [t.code, t.name]));
  const s = data.summary;
  const month = monthName(data.month_start);

  const stats = [
    { label: "Customers", value: s.organizations, note: `${s.active} active · ${s.suspended} suspended` },
    { label: "Users", value: s.users },
    {
      label: `Usage in ${month}`,
      value: s.usage_succeeded.toLocaleString("en-US"),
      note: s.usage_failed > 0 ? `${s.usage_failed} failed` : "no failures",
    },
    { label: "Estimated revenue", value: usd(s.estimated_revenue), note: `${month}, placeholder prices` },
  ];

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader>
              <CardDescription>{stat.label}</CardDescription>
              <CardTitle className="text-2xl tabular-nums">{stat.value}</CardTitle>
              {stat.note && <p className="text-xs text-muted-foreground">{stat.note}</p>}
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card className="py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Organization</TableHead>
              <TableHead>Owner</TableHead>
              <TableHead className="text-right">Members</TableHead>
              <TableHead>Tools</TableHead>
              <TableHead className="text-right">Usage</TableHead>
              <TableHead className="text-right">Est. revenue</TableHead>
              <TableHead>Joined</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.organizations.map((org) => (
              <TableRow key={org.id}>
                <TableCell className="font-medium">
                  <Link href={`/platform/${org.id}`} className="hover:underline">
                    {org.name}
                  </Link>
                  {org.status !== "active" && (
                    <Badge variant="destructive" className="ml-2">
                      Suspended
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{org.owner ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{org.members}</TableCell>
                <TableCell>
                  {org.tools.length === 0 ? (
                    <span className="text-muted-foreground">None</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {org.tools.map((t) => (
                        <Badge key={t} variant="secondary">
                          {toolNames[t] ?? t}
                        </Badge>
                      ))}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {org.usage_succeeded}
                  {org.usage_failed > 0 && <span className="text-destructive"> / {org.usage_failed} failed</span>}
                </TableCell>
                <TableCell className="text-right tabular-nums">{usd(org.estimated_revenue)}</TableCell>
                <TableCell className="text-muted-foreground">{day(org.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </>
  );
}
