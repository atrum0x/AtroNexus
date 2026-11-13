import { PowerOff } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { TableSkeleton } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CAPTURE, isToolEnabled } from "@/lib/tools";

// Every capture admin page needs the tool switched on; the API refuses otherwise.
export default function CaptureLayout({ children }: LayoutProps<"/capture">) {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <RequireCapture>{children}</RequireCapture>
    </Suspense>
  );
}

async function RequireCapture({ children }: { children: React.ReactNode }) {
  if (await isToolEnabled(CAPTURE)) return children;
  return (
    <Card className="max-w-xl">
      <CardContent className="flex flex-col items-start gap-3 py-2">
        <PowerOff className="size-6 text-muted-foreground" />
        <div className="grid gap-1">
          <h1 className="text-lg font-semibold">The capture page is switched off</h1>
          <p className="text-sm text-muted-foreground">
            Its links don&apos;t work while it&apos;s off. Your capture pages and their history are kept, and come
            back when you switch it on again.
          </p>
        </div>
        <Button render={<Link href="/tools" />} nativeButton={false}>
          Go to Tools
        </Button>
      </CardContent>
    </Card>
  );
}
