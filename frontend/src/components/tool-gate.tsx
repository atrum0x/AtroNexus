import { PowerOff } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { isToolEnabled } from "@/lib/tools";

/**
 * Shows a tool's pages only while the organization has it switched on (its
 * API refuses otherwise). Render inside <Suspense>, typically from the tool's
 * section layout.
 */
export async function ToolGate({
  code,
  name,
  children,
}: {
  code: string;
  name: string;
  children: React.ReactNode;
}) {
  if (await isToolEnabled(code)) return children;
  return (
    <Card className="max-w-xl">
      <CardContent className="flex flex-col items-start gap-3 py-2">
        <PowerOff className="size-6 text-muted-foreground" />
        <div className="grid gap-1">
          <h1 className="text-lg font-semibold">{name} is switched off</h1>
          <p className="text-sm text-muted-foreground">
            Its links don&apos;t work while it&apos;s off. Its settings and history are kept, and come back when
            you switch it on again.
          </p>
        </div>
        <Button render={<Link href="/tools" />} nativeButton={false}>
          Go to Tools
        </Button>
      </CardContent>
    </Card>
  );
}
