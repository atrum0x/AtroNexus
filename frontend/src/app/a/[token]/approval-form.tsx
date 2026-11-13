"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useState, useTransition } from "react";

import type { RejectReason } from "@/api/generated/models";
import { StatusBlock } from "@/components/status-icon";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { loadRejectReasons, sendDecision } from "./actions";

type Mode = "choose" | "confirm-approve" | "reject";

/**
 * Approve (after a confirm) or reject (with a reason). Nothing happens just by
 * opening the page, so email scanners that open links can't decide anything.
 */
export function ApprovalForm({ token }: { token: string }) {
  const [mode, setMode] = useState<Mode>("choose");
  const [done, setDone] = useState<{ result: string; message: string }>();
  const [error, setError] = useState<string>();
  const [reasons, setReasons] = useState<RejectReason[]>();
  const [reasonId, setReasonId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [pending, start] = useTransition();

  if (done) {
    const approved = done.result === "APPROVED";
    const rejected = done.result === "REJECTED";
    return (
      <StatusBlock
        icon={approved ? CheckCircle2 : rejected ? XCircle : CheckCircle2}
        tone={approved ? "success" : rejected ? "error" : "neutral"}
        title={approved ? "Approved" : rejected ? "Rejected" : "Nothing to do"}
      >
        {done.message} You can close this page.
      </StatusBlock>
    );
  }

  function decide(decision: "approve" | "reject") {
    setError(undefined);
    start(async () => {
      const res = await sendDecision(token, decision, reasonId ?? undefined, note);
      if (res.ok) setDone({ result: res.result, message: res.message });
      else setError(res.message);
    });
  }

  function openReject() {
    setMode("reject");
    setError(undefined);
    if (!reasons) {
      start(async () => {
        const res = await loadRejectReasons(token);
        if (res.reasons) setReasons(res.reasons);
        else setError(res.error);
      });
    }
  }

  const reasonItems = (reasons ?? []).map((r) => ({ value: r.id, label: r.description }));

  return (
    <div className="grid gap-3">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {mode === "choose" && (
        <>
          <Button size="lg" className="h-11" onClick={() => setMode("confirm-approve")}>
            <CheckCircle2 />
            Approve
          </Button>
          <Button size="lg" variant="outline" className="h-11" onClick={openReject}>
            <XCircle />
            Reject
          </Button>
        </>
      )}

      {mode === "confirm-approve" && (
        <>
          <p className="text-center text-sm text-muted-foreground">
            IFS records the approval in your name, with your authorization limits.
          </p>
          <Button size="lg" className="h-11" disabled={pending} onClick={() => decide("approve")}>
            {pending ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
            Yes, approve
          </Button>
          <Button size="lg" variant="ghost" className="h-11" disabled={pending} onClick={() => setMode("choose")}>
            Back
          </Button>
        </>
      )}

      {mode === "reject" && (
        <>
          <div className="grid gap-2">
            <Label htmlFor="reason">Reason</Label>
            <Select items={reasonItems} value={reasonId} onValueChange={setReasonId} disabled={pending || !reasons}>
              <SelectTrigger id="reason" className="h-11 w-full">
                <SelectValue placeholder={reasons ? "Pick a reason" : "Loading reasons…"} />
              </SelectTrigger>
              <SelectContent>
                {reasonItems.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="note">Note (optional)</Label>
            <Textarea
              id="note"
              rows={3}
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={pending}
              placeholder="For example: ask for another quote"
            />
          </div>
          <Button
            size="lg"
            variant="destructive"
            className="h-11"
            disabled={pending || !reasonId}
            onClick={() => decide("reject")}
          >
            {pending ? <Loader2 className="animate-spin" /> : <XCircle />}
            Reject
          </Button>
          <Button size="lg" variant="ghost" className="h-11" disabled={pending} onClick={() => setMode("choose")}>
            Back
          </Button>
        </>
      )}
    </div>
  );
}
