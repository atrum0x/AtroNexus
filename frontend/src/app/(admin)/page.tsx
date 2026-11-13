import { AlertTriangle, ArrowRight, CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { getOverview } from "@/api/generated/endpoints/overview/overview";
import type { ChecklistItem, CostEstimate, Overview, RecentError, ToolUsageOut } from "@/api/generated/models";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";

export default function DashboardPage() {
  return (
    <div className="grid gap-8">
      <Suspense fallback={<div className="h-12 w-64 animate-pulse rounded-md bg-muted" />}>
        <Greeting />
      </Suspense>
      <Suspense fallback={<div className="h-64 animate-pulse rounded-xl bg-muted" />}>
        <Dashboard />
      </Suspense>
    </div>
  );
}

async function Greeting() {
  const user = await getCurrentUser();
  return (
    <div className="grid gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome, {user.name ?? user.username ?? user.email}</h1>
      <p className="text-sm text-muted-foreground">{user.organization.name}</p>
    </div>
  );
}

async function Dashboard() {
  const data: Overview = await getOverview();
  const month = new Date(data.month_start).toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });

  return (
    <>
      <Checklist items={data.checklist} />

      {data.usage.length > 0 && (
        <section className="grid gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Usage in {month}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.usage.map((u) => (
              <UsageCard key={u.tool} usage={u} />
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <RecentErrors errors={data.recent_errors} />
        {data.estimate && <Estimate estimate={data.estimate} month={month} />}
      </div>
    </>
  );
}

function Checklist({ items }: { items: ChecklistItem[] }) {
  const done = items.filter((i) => i.done).length;
  if (done === items.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Get set up</CardTitle>
        <CardDescription>
          {done} of {items.length} done
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-2 text-sm">
          {items.map((item) => (
            <li key={item.key} className="flex items-center gap-2">
              {item.done ? (
                <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
              ) : (
                <Circle className="size-4 shrink-0 text-muted-foreground" />
              )}
              {item.done || item.key === "verify_email" ? (
                <span className={item.done ? "text-muted-foreground line-through" : undefined}>
                  {item.label}
                  {!item.done && <span className="text-muted-foreground"> (use the link we emailed you)</span>}
                </span>
              ) : (
                <Link href={item.link} className="flex items-center gap-1 font-medium hover:underline">
                  {item.label}
                  <ArrowRight className="size-3.5" />
                </Link>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function UsageCard({ usage }: { usage: ToolUsageOut }) {
  const change = usage.succeeded - usage.last_month_succeeded;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardDescription>{usage.name}</CardDescription>
          {!usage.enabled && <Badge variant="outline">Off</Badge>}
        </div>
        <CardTitle className="text-3xl tabular-nums">{usage.succeeded.toLocaleString("en-US")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-0.5 text-sm text-muted-foreground">
        <span>sent to IFS this month</span>
        {usage.failed > 0 && (
          <span className="text-destructive">{usage.failed.toLocaleString("en-US")} failed</span>
        )}
        <span>
          {usage.last_month_succeeded.toLocaleString("en-US")} last month
          {change !== 0 && usage.last_month_succeeded > 0 && (
            <span> ({change > 0 ? `+${change}` : change})</span>
          )}
        </span>
      </CardContent>
    </Card>
  );
}

function RecentErrors({ errors }: { errors: RecentError[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent errors</CardTitle>
        <CardDescription>The latest things IFS didn&apos;t accept.</CardDescription>
      </CardHeader>
      <CardContent>
        {errors.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="size-4 text-emerald-600" />
            Nothing has failed.
          </p>
        ) : (
          <ul className="grid gap-3">
            {errors.map((e, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                <div className="grid min-w-0 gap-0.5">
                  <Link href={e.link} className="truncate font-medium hover:underline">
                    {e.title}
                  </Link>
                  <span className="text-muted-foreground">{e.message}</span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(e.at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function usd(value: string | number): string {
  return Number(value).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function Estimate({ estimate, month }: { estimate: CostEstimate; month: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Estimated cost for {month}</CardTitle>
        <CardDescription>Placeholder prices. Nothing is charged yet.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        {estimate.lines.length === 0 ? (
          <p className="text-muted-foreground">
            No tools are switched on.{" "}
            <Link href="/tools" className="font-medium text-foreground hover:underline">
              Pick one
            </Link>
            .
          </p>
        ) : (
          <>
            <ul className="grid gap-2">
              {estimate.lines.map((line) => (
                <li key={line.tool} className="flex items-start justify-between gap-4">
                  <span className="grid">
                    <span>{line.name}</span>
                    {line.usage_price && (
                      <span className="text-xs text-muted-foreground">
                        {usd(line.monthly_fee)} + {line.usage_count.toLocaleString("en-US")} {line.usage_unit}s ×{" "}
                        {usd(line.usage_price)}
                      </span>
                    )}
                  </span>
                  <span className="tabular-nums">{usd(line.total)}</span>
                </li>
              ))}
            </ul>
            <div className="flex justify-between border-t pt-3 font-medium">
              <span>Total</span>
              <span className="tabular-nums">{usd(estimate.total)}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
