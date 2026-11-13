"use client";

import { CheckCircle2, Loader2, MapPin, MapPinOff, RotateCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { sendCapture, type CaptureInput } from "./actions";

type Step =
  | { kind: "locating" }
  | { kind: "no-location"; reason: "denied" | "unavailable"; message: string }
  | { kind: "sending" }
  | { kind: "done"; withLocation: boolean }
  | { kind: "failed"; message: string; input: CaptureInput };

function deviceDetails() {
  const nav = navigator as Navigator & { userAgentData?: { platform?: string } };
  return {
    platform: nav.userAgentData?.platform || navigator.platform || null,
    language: navigator.language || null,
    time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
    screen: `${window.screen.width}x${window.screen.height}`,
  };
}

function locationError(err: GeolocationPositionError): {
  reason: "denied" | "unavailable";
  message: string;
} {
  if (err.code === err.PERMISSION_DENIED) {
    return {
      reason: "denied",
      message:
        "Location access is blocked. Allow it for this site in the browser's address bar, then try again.",
    };
  }
  if (err.code === err.TIMEOUT) {
    return { reason: "unavailable", message: "Finding your location took too long." };
  }
  return { reason: "unavailable", message: "Your device couldn't find its location." };
}

export function CaptureFlow({
  publicId,
  requestId,
  targetName,
}: {
  publicId: string;
  requestId: string;
  targetName: string;
}) {
  const [step, setStep] = useState<Step>({ kind: "locating" });
  const started = useRef(false);

  const send = useCallback(
    async (input: CaptureInput) => {
      setStep({ kind: "sending" });
      const result = await sendCapture(publicId, requestId, input);
      if (result.ok) {
        setStep({ kind: "done", withLocation: input.status === "captured" });
        // Closes the tab when IFS opened it as a pop-up. Browsers ignore this otherwise.
        setTimeout(() => window.close(), 2500);
      } else {
        setStep({ kind: "failed", message: result.message, input });
      }
    },
    [publicId, requestId],
  );

  const locate = useCallback(() => {
    setStep({ kind: "locating" });
    if (!window.isSecureContext || !("geolocation" in navigator)) {
      setStep({
        kind: "no-location",
        reason: "unavailable",
        message: window.isSecureContext
          ? "This browser can't share its location."
          : "Location only works when this page is opened over HTTPS.",
      });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        void send({
          status: "captured",
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          ...deviceDetails(),
        }),
      (err) => setStep({ kind: "no-location", ...locationError(err) }),
      { enableHighAccuracy: true, timeout: 20_000, maximumAge: 0 },
    );
  }, [send]);

  useEffect(() => {
    // Effects run twice in development; ask for the location only once.
    if (started.current) return;
    started.current = true;
    locate();
  }, [locate]);

  const sendWithoutLocation = (reason: "denied" | "unavailable", message: string) =>
    void send({ status: reason, location_error: message, ...deviceDetails() });

  return (
    <div className="flex flex-col items-center gap-4 py-4 text-center">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {targetName}
      </p>

      {step.kind === "locating" && (
        <Status icon={<MapPin className="size-8 animate-pulse text-primary" />} title="Finding your location">
          If your browser asks, choose <strong>Allow</strong>.
        </Status>
      )}

      {step.kind === "sending" && (
        <Status icon={<Loader2 className="size-8 animate-spin text-muted-foreground" />} title="Saving to IFS">
          This takes a few seconds.
        </Status>
      )}

      {step.kind === "done" && (
        <Status
          icon={<CheckCircle2 className="size-8 text-emerald-600" />}
          title={step.withLocation ? "Location captured" : "Saved without a location"}
        >
          You can close this tab and go back to IFS.
        </Status>
      )}

      {step.kind === "no-location" && (
        <>
          <Status icon={<MapPinOff className="size-8 text-muted-foreground" />} title="No location yet">
            {step.message}
          </Status>
          <div className="flex w-full flex-col gap-2">
            <Button onClick={locate}>
              <RotateCw />
              Try again
            </Button>
            <Button variant="ghost" onClick={() => sendWithoutLocation(step.reason, step.message)}>
              Continue without location
            </Button>
          </div>
        </>
      )}

      {step.kind === "failed" && (
        <>
          <Status icon={<XCircle className="size-8 text-destructive" />} title="IFS didn't accept it">
            {step.message}
          </Status>
          <Button className="w-full" onClick={() => void send(step.input)}>
            <RotateCw />
            Try again
          </Button>
        </>
      )}

      <p className="font-mono text-xs text-muted-foreground">Request {requestId}</p>
    </div>
  );
}

function Status({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <>
      {icon}
      <div className="grid gap-1">
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{children}</p>
      </div>
    </>
  );
}
