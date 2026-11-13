import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";
import { canManage } from "@/lib/roles";
import { APPROVALS, CAPTURE, formatPrice, getTools } from "@/lib/tools";

import { ToolSwitch } from "./tool-switch";

// Where each built tool is set up once it's on.
const SETUP_LINKS: Record<string, { href: string; label: string }> = {
  [CAPTURE]: { href: "/capture", label: "Set up capture pages" },
  [APPROVALS]: { href: "/approvals", label: "Set up approvals" },
};

export default function ToolsPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Tools"
        description="Switch on the tools your organization uses. Each tool is a monthly subscription; no payment is taken yet."
      />
      <Suspense fallback={<TableSkeleton />}>
        <ToolList />
      </Suspense>
    </div>
  );
}

async function ToolList() {
  const [tools, user] = await Promise.all([getTools(), getCurrentUser()]);
  const manager = canManage(user);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {tools.map((tool) => {
        const price = formatPrice(tool);
        const setup = SETUP_LINKS[tool.code];
        return (
          <Card key={tool.code} className={tool.available ? undefined : "opacity-70"}>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <CardTitle>{tool.name}</CardTitle>
                {!tool.available ? (
                  <Badge variant="outline">Coming soon</Badge>
                ) : manager ? (
                  <ToolSwitch code={tool.code} name={tool.name} enabled={tool.enabled} />
                ) : (
                  <Badge variant={tool.enabled ? "secondary" : "outline"}>{tool.enabled ? "On" : "Off"}</Badge>
                )}
              </div>
              <CardDescription>{tool.description}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-baseline gap-x-2 text-sm">
              <span className="font-medium">{price.monthly}</span>
              {price.usage && <span className="text-muted-foreground">{price.usage}</span>}
            </CardContent>
            {tool.enabled && setup && (
              <CardFooter>
                <Link href={setup.href} className="flex items-center gap-1 text-sm font-medium hover:underline">
                  {setup.label}
                  <ArrowRight className="size-4" />
                </Link>
              </CardFooter>
            )}
          </Card>
        );
      })}
    </div>
  );
}
