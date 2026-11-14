"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";

import { refreshTemplate } from "../actions";

/** Asks WhatsApp for the review status now; a draft is submitted again. */
export function RefreshButton({ id, label }: { id: number; label: string }) {
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();
  return (
    <div className="grid justify-items-start gap-1.5">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={pending}
        onClick={() =>
          start(async () => {
            setError((await refreshTemplate(id)).error);
          })
        }
      >
        {pending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
        {label}
      </Button>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
