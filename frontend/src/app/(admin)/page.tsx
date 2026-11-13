import { ArrowRight, Blocks, MapPin, PlugZap, Users } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";
import { CAPTURE, getTools } from "@/lib/tools";

type Tile = { href: string; icon: typeof MapPin; title: string; description: string };

const CAPTURE_TILE: Tile = {
  href: "/capture",
  icon: MapPin,
  title: "Capture page",
  description:
    "Opened from a button in IFS. Reads the user's location, IP address and device, and writes them back to the IFS record.",
};

const ALWAYS: Tile[] = [
  {
    href: "/connections",
    icon: PlugZap,
    title: "IFS connections",
    description: "The IFS environments and service users the tools sign in as.",
  },
  {
    href: "/tools",
    icon: Blocks,
    title: "Tools",
    description: "Switch tools on and off, and see what each one costs.",
  },
  {
    href: "/team",
    icon: Users,
    title: "Team",
    description: "Invite people and choose what they can change.",
  },
];

export default function HomePage() {
  return (
    <div className="grid gap-6">
      <Suspense fallback={<div className="h-8 w-64 animate-pulse rounded-md bg-muted" />}>
        <Greeting />
      </Suspense>
      <Suspense fallback={<div className="h-40 animate-pulse rounded-xl bg-muted" />}>
        <Tiles />
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

async function Tiles() {
  const tools = await getTools();
  const enabled = tools.filter((t) => t.enabled);
  const tiles = [...(enabled.some((t) => t.code === CAPTURE) ? [CAPTURE_TILE] : []), ...ALWAYS];

  return (
    <div className="grid gap-4">
      {enabled.length === 0 && (
        <Link href="/tools" className="group">
          <Card className="border-dashed transition-colors group-hover:bg-muted/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                Pick your first tool
                <ArrowRight className="size-4" />
              </CardTitle>
              <CardDescription>
                No tools are switched on yet. Start with the capture page: it reads a user&apos;s location from a
                button in IFS.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {tiles.map((tile) => (
          <Link key={tile.href} href={tile.href} className="group">
            <Card className="h-full transition-colors group-hover:bg-muted/50">
              <CardHeader>
                <tile.icon className="mb-2 size-5 text-muted-foreground" />
                <CardTitle className="flex items-center gap-1.5">
                  {tile.title}
                  <ArrowRight className="size-4 opacity-0 transition-opacity group-hover:opacity-100" />
                </CardTitle>
                <CardDescription>{tile.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
