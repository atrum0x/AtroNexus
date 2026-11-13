"use client";

import { useState, useTransition } from "react";

import { Switch } from "@/components/ui/switch";

import { setToolEnabled } from "./actions";

/** Switches a tool on or off right away; rolls back and shows why if the server refuses. */
export function ToolSwitch({ code, name, enabled }: { code: string; name: string; enabled: boolean }) {
  const [on, setOn] = useState(enabled);
  const [error, setError] = useState<string>();
  const [pending, startTransition] = useTransition();

  function change(next: boolean) {
    setOn(next);
    setError(undefined);
    startTransition(async () => {
      const result = await setToolEnabled(code, next);
      if (result.error) {
        setOn(!next);
        setError(result.error);
      }
    });
  }

  return (
    <div className="grid justify-items-end gap-1">
      <label className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">{on ? "On" : "Off"}</span>
        <Switch checked={on} onCheckedChange={change} disabled={pending} aria-label={`${name} on or off`} />
      </label>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
