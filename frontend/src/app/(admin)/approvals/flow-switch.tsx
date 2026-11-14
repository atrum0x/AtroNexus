"use client";

import { useState, useTransition } from "react";

import { Switch } from "@/components/ui/switch";

import { setFlowEnabled } from "./actions";

/** Switches one approval type on or off right away; rolls back and shows why if the server refuses. */
export function FlowSwitch({ code, name, enabled }: { code: string; name: string; enabled: boolean }) {
  const [on, setOn] = useState(enabled);
  const [error, setError] = useState<string>();
  const [pending, startTransition] = useTransition();

  function change(next: boolean) {
    setOn(next);
    setError(undefined);
    startTransition(async () => {
      const result = await setFlowEnabled(code, next);
      if (result.error) {
        setOn(!next);
        setError(result.error);
      }
    });
  }

  return (
    <div className="grid justify-items-end gap-1">
      <Switch checked={on} onCheckedChange={change} disabled={pending} aria-label={`${name} on or off`} />
      {error && <p className="max-w-48 text-right text-xs text-destructive">{error}</p>}
    </div>
  );
}
