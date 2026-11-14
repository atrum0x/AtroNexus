"use client";

import { AlertCircle, CheckCircle2, Loader2, Send } from "lucide-react";
import { useState, useTransition } from "react";

import type { SentMessageOut } from "@/api/generated/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { testScenario } from "../actions";
import { nest } from "./fields";

/** Sends the scenario once with values typed here, as if IFS had called it. */
export function TestSend({ scenarioId, fields }: { scenarioId: number; fields: string[] }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{ message?: SentMessageOut; error?: string }>();
  const [pending, start] = useTransition();

  function send(e: React.FormEvent) {
    e.preventDefault();
    setResult(undefined);
    start(async () => setResult(await testScenario(scenarioId, nest(values))));
  }

  return (
    <form onSubmit={send} className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((f) => (
          <label key={f} className="grid gap-1.5 text-sm">
            <code className="font-mono text-xs text-muted-foreground">{f}</code>
            <Input
              value={values[f] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f]: e.target.value }))}
              placeholder={f.toLowerCase().includes("phone") ? "+94771234567" : ""}
            />
          </label>
        ))}
      </div>
      {result?.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{result.error}</AlertDescription>
        </Alert>
      )}
      {result?.message && (
        <Alert variant={result.message.status === "failed" ? "destructive" : "default"}>
          {result.message.status === "failed" ? <AlertCircle /> : <CheckCircle2 />}
          <AlertDescription>
            {result.message.status === "failed"
              ? `WhatsApp didn't send it: ${result.message.error}`
              : `Sent to +${result.message.to_phone}. Delivery shows in the log below.`}
          </AlertDescription>
        </Alert>
      )}
      <div>
        <Button type="submit" variant="outline" disabled={pending}>
          {pending ? <Loader2 className="animate-spin" /> : <Send />}
          Send test
        </Button>
      </div>
    </form>
  );
}
