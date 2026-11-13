"use client";

import { CheckCircle2, Loader2, MapPin, MapPinOff, RotateCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { sendCapture, type CaptureInput } from "./actions";
import { StatusBlock } from "./status-icon";

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

type DeviceKind = "ios" | "android" | "other";

function deviceKind(): DeviceKind {
  const ua = navigator.userAgent;
  // iPadOS reports itself as a Mac; touch support gives it away.
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) {
    return "ios";
  }
  if (/Android/.test(ua)) return "android";
  return "other";
}

// Browsers built into other apps (WhatsApp, Teams, Outlook, Facebook, ...)
// often can't share the location at all, so point the user to a real browser.
function inAppBrowser(): boolean {
  const ua = navigator.userAgent;
  return (
    /FBAN|FBAV|Instagram|Line\/|WhatsApp|MicroMessenger|Teams|Outlook|LinkedInApp|Snapchat/i.test(ua) ||
    /; wv\)/.test(ua) ||
    (/iPhone|iPad|iPod/.test(ua) && !/Safari\//.test(ua))
  );
}

function openInBrowserHint(kind: DeviceKind): string {
  return kind === "ios"
    ? " If you opened this link from another app, open it in Safari instead."
    : kind === "android"
      ? " If you opened this link from another app, open it in Chrome instead."
      : "";
}

function locationError(err: GeolocationPositionError): {
  reason: "denied" | "unavailable";
  message: string;
} {
  const kind = deviceKind();
  const inApp = inAppBrowser() ? openInBrowserHint(kind) : "";
  if (err.code === err.PERMISSION_DENIED) {
    const how =
      kind === "ios"
        ? "Location access is blocked. In Safari, tap aA in the address bar, then Website Settings, and set Location to Allow. If that doesn't help, turn on Settings > Privacy & Security > Location Services, and set Safari Websites to While Using the App."
        : kind === "android"
          ? "Location access is blocked. Tap the icon next to the address, open Permissions, and allow Location. Also check that Location is turned on in the phone's quick settings."
          : "Location access is blocked. Allow it for this site in the browser's address bar.";
    return { reason: "denied", message: `${how} Then try again.${inApp}` };
  }
  if (err.code === err.TIMEOUT) {
    return {
      reason: "unavailable",
      message: `Finding your location took too long. Moving near a window or outside can help.${inApp}`,
    };
  }
  const off =
    kind === "other"
      ? "Your device couldn't find its location."
      : "Your phone couldn't find its location. Check that Location (GPS) is turned on.";
  return { reason: "unavailable", message: `${off}${inApp}` };
}

function getPosition(options: PositionOptions): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) =>
    navigator.geolocation.getCurrentPosition(resolve, reject, options),
  );
}

// Tries GPS first. Indoors that often runs out of time on phones, so it then
// accepts a quicker, less precise fix (Wi-Fi or cell towers).
async function findPosition(): Promise<GeolocationPosition> {
  try {
    return await getPosition({ enableHighAccuracy: true, timeout: 15_000, maximumAge: 0 });
  } catch (err) {
    const e = err as GeolocationPositionError;
    if (e.code === e.PERMISSION_DENIED) throw err;
    return getPosition({ enableHighAccuracy: false, timeout: 15_000, maximumAge: 60_000 });
  }
}

// After this long without an answer, offer to carry on without a location.
const SLOW_AFTER_MS = 12_000;

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
  const [slow, setSlow] = useState(false);
  const started = useRef(false);
  // Ignores an answer from an earlier attempt once the user has moved on.
  const attempt = useRef(0);

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
    const current = ++attempt.current;
    setStep({ kind: "locating" });
    setSlow(false);
    if (!window.isSecureContext || !("geolocation" in navigator)) {
      setStep({
        kind: "no-location",
        reason: "unavailable",
        message: window.isSecureContext
          ? `This browser can't share its location.${openInBrowserHint(deviceKind())}`
          : "Location only works when this page is opened over HTTPS.",
      });
      return;
    }
    const slowTimer = setTimeout(() => {
      if (attempt.current === current) setSlow(true);
    }, SLOW_AFTER_MS);
    findPosition().then(
      (pos) => {
        clearTimeout(slowTimer);
        if (attempt.current !== current) return;
        void send({
          status: "captured",
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          ...deviceDetails(),
        });
      },
      (err: GeolocationPositionError) => {
        clearTimeout(slowTimer);
        if (attempt.current !== current) return;
        setStep({ kind: "no-location", ...locationError(err) });
      },
    );
  }, [send]);

  useEffect(() => {
    // Effects run twice in development; ask for the location only once.
    if (started.current) return;
    started.current = true;
    locate();
  }, [locate]);

  const sendWithoutLocation = (reason: "denied" | "unavailable", message: string) => {
    attempt.current++; // a late location answer must not send a second time
    void send({ status: reason, location_error: message, ...deviceDetails() });
  };

  return (
    <div className="flex flex-col items-center gap-6 py-2 text-center">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {targetName}
      </p>

      {step.kind === "locating" && (
        <>
          <StatusBlock icon={MapPin} tone="active" motion="pulse" title="Finding your location">
            If your browser asks, choose <strong>Allow</strong>.
          </StatusBlock>
          {slow && (
            <Button
              variant="ghost"
              size="lg"
              className="h-11 w-full"
              onClick={() =>
                sendWithoutLocation("unavailable", "The location didn't arrive in time.")
              }
            >
              Continue without location
            </Button>
          )}
        </>
      )}

      {step.kind === "sending" && (
        <StatusBlock icon={Loader2} tone="busy" motion="spin" title="Saving to IFS">
          This takes a few seconds.
        </StatusBlock>
      )}

      {step.kind === "done" && (
        <StatusBlock
          icon={CheckCircle2}
          tone="success"
          title={step.withLocation ? "Location captured" : "Saved without a location"}
        >
          You can close this tab and go back to IFS.
        </StatusBlock>
      )}

      {step.kind === "no-location" && (
        <>
          <StatusBlock icon={MapPinOff} tone="warning" title="No location yet">
            {step.message}
          </StatusBlock>
          <div className="flex w-full flex-col gap-2">
            <Button size="lg" className="h-11" onClick={locate}>
              <RotateCw />
              Try again
            </Button>
            <Button
              variant="ghost"
              size="lg"
              className="h-11"
              onClick={() => sendWithoutLocation(step.reason, step.message)}
            >
              Continue without location
            </Button>
          </div>
        </>
      )}

      {step.kind === "failed" && (
        <>
          <StatusBlock icon={XCircle} tone="error" title="Not saved yet">
            {step.message}
          </StatusBlock>
          <Button size="lg" className="h-11 w-full" onClick={() => void send(step.input)}>
            <RotateCw />
            Try again
          </Button>
        </>
      )}

      <p className="font-mono text-xs text-muted-foreground">Request {requestId}</p>
    </div>
  );
}
