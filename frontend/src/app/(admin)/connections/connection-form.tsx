"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useActionState, useState } from "react";

import type { IfsConnectionOut } from "@/api/generated/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { saveConnection, type ConnectionFormState } from "./actions";

const AUTH_TYPES = [
  { value: "oauth2", label: "OAuth2 client credentials (IFS Cloud)" },
  { value: "basic", label: "Username and password (basic auth)" },
];

export function ConnectionForm({
  connection,
  readOnly = false,
}: {
  connection?: IfsConnectionOut;
  /** For members: shows the settings without a way to change them. */
  readOnly?: boolean;
}) {
  const [state, action, pending] = useActionState<ConnectionFormState, FormData>(
    saveConnection.bind(null, connection?.id ?? null),
    {},
  );
  const locked = pending || readOnly;
  const v = { ...connection, ...state.values };
  const [authType, setAuthType] = useState<string>(v.auth_type ?? "oauth2");
  const isEdit = !!connection;

  return (
    <form action={action} className="grid gap-5">
      {state.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      <Field label="Name" htmlFor="name" hint="For example the customer and environment: Acme production.">
        <Input id="name" name="name" required defaultValue={v.name} disabled={locked} />
      </Field>

      <Field
        label="IFS base URL"
        htmlFor="base_url"
        hint="The address of the IFS Cloud environment, without a path."
      >
        <Input
          id="base_url"
          name="base_url"
          type="url"
          required
          placeholder="https://acme.ifs.cloud"
          defaultValue={v.base_url}
          disabled={locked}
        />
      </Field>

      <Field label="Sign-in method" htmlFor="auth_type">
        <Select
          name="auth_type"
          items={AUTH_TYPES}
          value={authType}
          onValueChange={(value) => value && setAuthType(value)}
          disabled={locked}
        >
          <SelectTrigger id="auth_type" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AUTH_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      {authType === "oauth2" ? (
        <>
          <Field
            label="Token URL"
            htmlFor="token_url"
            hint="Usually https://<ifs-host>/auth/realms/<realm>/protocol/openid-connect/token"
          >
            <Input
              id="token_url"
              name="token_url"
              type="url"
              required
              defaultValue={v.token_url ?? ""}
              disabled={locked}
            />
          </Field>
          <Field
            label="Client ID"
            htmlFor="client_id"
            hint="The IAM client set up in IFS for this service user."
          >
            <Input
              id="client_id"
              name="client_id"
              required
              defaultValue={v.client_id ?? ""}
              disabled={locked}
            />
          </Field>
        </>
      ) : (
        <Field label="Username" htmlFor="username">
          <Input
            id="username"
            name="username"
            required
            autoComplete="off"
            defaultValue={v.username ?? ""}
            disabled={locked}
          />
        </Field>
      )}

      <Field
        label={authType === "oauth2" ? "Client secret" : "Password"}
        htmlFor="secret"
        hint={
          isEdit
            ? "Leave empty to keep the saved one. It's stored encrypted and never shown again."
            : "Stored encrypted. It's never shown again after you save."
        }
      >
        <Input
          id="secret"
          name="secret"
          type="password"
          autoComplete="new-password"
          required={!isEdit}
          placeholder={isEdit ? "••••••••" : undefined}
          disabled={locked}
        />
      </Field>

      {!readOnly && (
        <div className="flex gap-2">
          <Button type="submit" disabled={locked}>
            {pending && <Loader2 className="animate-spin" />}
            {isEdit ? "Save changes" : "Add connection"}
          </Button>
          <Button variant="ghost" render={<Link href="/connections" />} nativeButton={false}>
            Cancel
          </Button>
        </div>
      )}
    </form>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
