"use client";

import { CheckCircle2, Loader2, PlugZap, XCircle } from "lucide-react";
import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type CheckState = { ok: boolean; message: string } | null;

/** A "Test" button that runs a server action and shows its result next to it. */
export function CheckButton({
  action,
  label = "Test connection",
}: {
  action: () => Promise<CheckState>;
  label?: string;
}) {
  const [result, run, pending] = useActionState<CheckState>(action, null);

  return (
    <div className="grid gap-2">
      <form action={run}>
        <Button type="submit" variant="outline" disabled={pending}>
          {pending ? <Loader2 className="animate-spin" /> : <PlugZap />}
          {pending ? "Testing…" : label}
        </Button>
      </form>
      {result && (
        <p
          className={cn(
            "flex items-start gap-1.5 text-sm",
            result.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive",
          )}
        >
          {result.ok ? (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
          ) : (
            <XCircle className="mt-0.5 size-4 shrink-0" />
          )}
          <span className="break-all">{result.message}</span>
        </p>
      )}
    </div>
  );
}
