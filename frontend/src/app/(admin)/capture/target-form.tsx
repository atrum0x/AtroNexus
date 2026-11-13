"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useActionState, useState } from "react";

import type {
  CaptureDefaults,
  CaptureTargetOut,
  IfsConnectionOut,
} from "@/api/generated/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { Field } from "../connections/connection-form";
import { saveTarget, type TargetFormState } from "./actions";

const METHODS = [
  { value: "PATCH", label: "PATCH: update the capture request record (recommended)" },
  { value: "POST", label: "POST: create a new record" },
];

export function TargetForm({
  target,
  connections,
  defaults,
  readOnly = false,
}: {
  target?: CaptureTargetOut;
  connections: IfsConnectionOut[];
  defaults: CaptureDefaults;
  /** For members: shows the settings without a way to change them. */
  readOnly?: boolean;
}) {
  const [state, action, pending] = useActionState<TargetFormState, FormData>(
    saveTarget.bind(null, target?.id ?? null),
    {},
  );
  const locked = pending || readOnly;
  const v = { ...target, ...state.values };
  const connectionItems = connections.map((c) => ({ value: String(c.id), label: c.name }));

  const [connectionId, setConnectionId] = useState<string | null>(
    v.connection_id ? String(v.connection_id) : (connectionItems[0]?.value ?? null),
  );
  const [method, setMethod] = useState<string>(v.http_method ?? defaults.http_method);
  const [enabled, setEnabled] = useState<boolean>(v.enabled ?? true);

  return (
    <form action={action} className="grid gap-5">
      {state.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      <Field label="Name" htmlFor="name" hint="For example: Purchase receipt location.">
        <Input id="name" name="name" required defaultValue={v.name} disabled={locked} />
      </Field>

      <Field label="IFS connection" htmlFor="connection_id" hint="The service user that writes the result.">
        <Select
          name="connection_id"
          items={connectionItems}
          value={connectionId}
          onValueChange={setConnectionId}
          required
          disabled={locked}
        >
          <SelectTrigger id="connection_id" className="w-full">
            <SelectValue placeholder="Pick a connection" />
          </SelectTrigger>
          <SelectContent>
            {connectionItems.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="Send with" htmlFor="http_method">
        <Select
          name="http_method"
          items={METHODS}
          value={method}
          onValueChange={(value) => value && setMethod(value)}
          disabled={locked}
        >
          <SelectTrigger id="http_method" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {METHODS.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field
        label="IFS endpoint"
        htmlFor="endpoint_path"
        hint={
          <>
            Path under the connection&apos;s base URL. <Code>{"{request_id}"}</Code> is replaced with
            the ID from the link.{" "}
            {method === "PATCH" &&
              "The record is read first, to check it exists and to get its ETag."}
          </>
        }
      >
        <Input
          id="endpoint_path"
          name="endpoint_path"
          required
          className="font-mono text-xs"
          defaultValue={v.endpoint_path ?? defaults.endpoint_path}
          disabled={locked}
        />
      </Field>

      <Field
        label="Request body"
        htmlFor="body_template"
        hint="JSON sent to IFS. Use the attribute names of your IFS entity (custom attributes start with Cf). A value that is exactly one placeholder keeps its type, so numbers stay numbers. For Text attributes in IFS, add :text, e.g. {latitude:text}."
      >
        <Textarea
          id="body_template"
          name="body_template"
          required
          rows={10}
          spellCheck={false}
          className="font-mono text-xs"
          defaultValue={v.body_template ?? defaults.body_template}
          disabled={locked}
        />
      </Field>

      <details className="rounded-lg border px-3 py-2 text-sm">
        <summary className="cursor-pointer font-medium">Placeholders you can use</summary>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
          {Object.entries(defaults.placeholders).map(([name, description]) => (
            <div key={name} className="contents">
              <dt>
                <Code>{`{${name}}`}</Code>
              </dt>
              <dd className="text-muted-foreground">{description}</dd>
            </div>
          ))}
        </dl>
      </details>

      <label className="flex items-center gap-3 text-sm">
        <Switch name="enabled" checked={enabled} onCheckedChange={setEnabled} disabled={locked} />
        <span>
          <span className="font-medium">Enabled.</span>{" "}
          <span className="text-muted-foreground">When off, links to this page stop working.</span>
        </span>
      </label>

      {!readOnly && (
        <div className="flex gap-2">
          <Button type="submit" disabled={pending || connections.length === 0}>
            {pending && <Loader2 className="animate-spin" />}
            {target ? "Save changes" : "Create capture page"}
          </Button>
          <Button variant="ghost" render={<Link href="/capture" />} nativeButton={false}>
            Cancel
          </Button>
        </div>
      )}
    </form>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{children}</code>;
}
