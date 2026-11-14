"use client";

import { KeyRound, Loader2 } from "lucide-react";
import { useState, useTransition } from "react";

import { CopyField } from "@/components/copy-field";
import { Button } from "@/components/ui/button";

/** Creates a hook key and shows it once, to paste into an IFS routing address. */
export function HookKey({
  hasKey,
  hint,
  readOnly,
  addressName,
  create,
}: {
  hasKey: boolean;
  hint: string | null;
  readOnly: boolean;
  /** The IFS routing address the key goes into, e.g. C_ATX_APPROVAL_ADDR. */
  addressName: string;
  create: () => Promise<{ key?: string; error?: string }>;
}) {
  const [key, setKey] = useState<string>();
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();

  function make() {
    if (hasKey && !window.confirm("Make a new key? The old one stops working at once, so IFS must get the new one.")) {
      return;
    }
    start(async () => {
      const res = await create();
      if (res.key) setKey(res.key);
      else setError(res.error);
    });
  }

  return (
    <div className="grid gap-2">
      {key ? (
        <>
          <CopyField value={key} label="hook key" />
          <p className="text-xs text-muted-foreground">
            Copy it now: it isn&apos;t shown again. Paste it into the bearer token of the routing address {addressName}{" "}
            in IFS.
          </p>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          {hasKey ? `A key ending in …${hint} is set.` : "No key yet."}
        </p>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
      {!readOnly && !key && (
        <div>
          <Button type="button" variant="outline" disabled={pending} onClick={make}>
            {pending ? <Loader2 className="animate-spin" /> : <KeyRound />}
            {hasKey ? "Make a new key" : "Create hook key"}
          </Button>
        </div>
      )}
    </div>
  );
}
