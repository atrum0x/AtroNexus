"use client";

import { Check, Copy } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

const subscribe = () => () => {};

/** The URL to put in the IFS custom command, built from this site's own address. */
export function CaptureLink({ publicId }: { publicId: string }) {
  const origin = useSyncExternalStore(
    subscribe,
    () => window.location.origin,
    () => "",
  );
  const [copied, setCopied] = useState(false);
  // ${RequestId} is IFS's syntax for inserting the record's attribute value.
  const url = `${origin}/c/${publicId}/\${RequestId}`;

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex items-center gap-2">
      <code className="min-w-0 flex-1 truncate rounded-md border bg-muted/50 px-3 py-2 font-mono text-xs">
        {url}
      </code>
      <Button type="button" variant="outline" size="icon" onClick={copy} aria-label="Copy link">
        {copied ? <Check /> : <Copy />}
      </Button>
    </div>
  );
}
