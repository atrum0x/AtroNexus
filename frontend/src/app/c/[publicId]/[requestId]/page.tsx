import { CheckCircle2, Link2Off } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getCaptureLink } from "@/api/generated/endpoints/capture-public/capture-public";
import { Card, CardContent } from "@/components/ui/card";

import { CaptureFlow } from "./capture-flow";

export const metadata: Metadata = {
  title: "Capture location · AtroNexus",
  robots: { index: false, follow: false },
};

export default function CapturePage({ params }: PageProps<"/c/[publicId]/[requestId]">) {
  return (
    <main className="flex flex-1 items-center justify-center bg-muted/40 px-4 py-12">
      <Card className="w-full max-w-sm">
        <CardContent>
          <Suspense fallback={<div className="h-32 animate-pulse rounded-lg bg-muted" />}>
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
    link = await getCaptureLink(publicId, requestId);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
      return (
        <Message icon={<Link2Off className="size-8 text-muted-foreground" />} title="This link isn't valid">
          Go back to IFS and open it again from the record.
        </Message>
      );
    }
    throw err;
  }

  if (link.already_sent) {
    return (
      <Message icon={<CheckCircle2 className="size-8 text-emerald-600" />} title="Already captured">
        This request was already saved to IFS. You can close this tab.
      </Message>
    );
  }

  return <CaptureFlow publicId={publicId} requestId={requestId} targetName={link.target_name} />;
}

function Message({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-4 text-center">
      {icon}
      <h1 className="text-lg font-semibold">{title}</h1>
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}
