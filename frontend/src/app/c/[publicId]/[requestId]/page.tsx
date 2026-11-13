import { CheckCircle2, Hourglass, Link2Off, type LucideIcon } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getCaptureLink } from "@/api/generated/endpoints/capture-public/capture-public";
import { Card, CardContent } from "@/components/ui/card";
import { clientIpHeaders } from "@/lib/client-ip";

import { CaptureFlow } from "./capture-flow";
import { StatusBlock, type Tone } from "./status-icon";

export const metadata: Metadata = {
  title: "Capture location · AtroNexus",
  robots: { index: false, follow: false },
};

export default function CapturePage({ params }: PageProps<"/c/[publicId]/[requestId]">) {
  return (
    // Opened on phones from IFS, so: big touch targets, and room for the
    // iPhone home bar (safe-area inset) at the bottom.
    <main className="flex min-h-svh flex-1 flex-col items-center justify-center gap-6 bg-muted/40 px-4 pt-10 pb-[max(2.5rem,env(safe-area-inset-bottom))]">
      <div className="flex items-center gap-2 text-sm font-semibold tracking-tight">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-xs text-primary-foreground">
          A
        </div>
        AtroNexus
      </div>
      <Card className="w-full max-w-sm">
        <CardContent className="px-6 py-4">
          <Suspense fallback={<div className="h-56 animate-pulse rounded-lg bg-muted" />}>
            <CaptureLoader params={params} />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}

async function CaptureLoader({
  params,
}: {
  params: Promise<{ publicId: string; requestId: string }>;
}) {
  const { publicId, requestId } = await params;

  let link;
  try {
    link = await getCaptureLink(publicId, requestId, { headers: await clientIpHeaders() });
  } catch (err) {
    if (err instanceof ApiError && err.status === 429) {
      return (
        <Message icon={Hourglass} tone="warning" title="Too many attempts">
          Wait a minute, then open the link again.
        </Message>
      );
    }
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
      return (
        <Message icon={Link2Off} tone="neutral" title="This link isn't valid">
          Go back to IFS and open it again from the record.
        </Message>
      );
    }
    throw err;
  }

  if (link.already_sent) {
    return (
      <Message icon={CheckCircle2} tone="success" title="Already captured">
        This request was already saved to IFS. You can close this tab.
      </Message>
    );
  }

  return <CaptureFlow publicId={publicId} requestId={requestId} targetName={link.target_name} />;
}

function Message({
  icon,
  tone,
  title,
  children,
}: {
  icon: LucideIcon;
  tone: Tone;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-2">
      <StatusBlock icon={icon} tone={tone} title={title}>
        {children}
      </StatusBlock>
    </div>
  );
}
