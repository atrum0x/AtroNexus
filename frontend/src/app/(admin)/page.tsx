import { ArrowRight, MapPin, PlugZap } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";

const TOOLS = [
  {
    href: "/capture",
    icon: MapPin,
    title: "Capture page",
    description:
      "Opened from a button in IFS. Reads the user's location, IP address and device, and writes them back to the IFS record.",
  },
  {
    href: "/connections",
    icon: PlugZap,
    title: "IFS connections",
    description: "The IFS environments and service users the tools sign in as.",
  },
];

export default function HomePage() {
  return (
    <div className="grid gap-6">
      <Suspense fallback={<div className="h-8 w-64 animate-pulse rounded-md bg-muted" />}>
        <Greeting />
      </Suspense>
      <div className="grid gap-4 sm:grid-cols-2">
        {TOOLS.map((tool) => (
          <Link key={tool.href} href={tool.href} className="group">
            <Card className="h-full transition-colors group-hover:bg-muted/50">
              <CardHeader>
                <tool.icon className="mb-2 size-5 text-muted-foreground" />
                <CardTitle className="flex items-center gap-1.5">
                  {tool.title}
                  <ArrowRight className="size-4 opacity-0 transition-opacity group-hover:opacity-100" />
                </CardTitle>
                <CardDescription>{tool.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

async function Greeting() {
  const user = await getCurrentUser();
  return (
    <div className="grid gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome, {user.username}</h1>
      <p className="text-sm text-muted-foreground">{user.organization.name}</p>
    </div>
  );
}
