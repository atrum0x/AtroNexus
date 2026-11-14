"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useState, useTransition } from "react";

import type { ScenarioOut, TemplateOut } from "@/api/generated/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { saveScenario } from "../actions";
import { TemplatePreview } from "../templates/template-preview";
import { fieldsIn, plsqlCall } from "./fields";

function Row({ label, hint, children }: { label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:items-center sm:gap-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="grid gap-1">
        {children}
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );
}

/**
 * A scenario: a code IFS calls, the template, and which IFS values fill each
 * of the template's variables.
 */
export function ScenarioForm({
  scenario,
  templates,
  readOnly = false,
}: {
  scenario?: ScenarioOut;
  templates: TemplateOut[];
  readOnly?: boolean;
}) {
  const [code, setCode] = useState(scenario?.code ?? "");
  const [name, setName] = useState(scenario?.name ?? "");
  const [templateId, setTemplateId] = useState<string | null>(scenario ? String(scenario.template_id) : null);
  const [recipient, setRecipient] = useState(scenario?.recipient ?? "{phone}");
  const [header, setHeader] = useState(scenario?.header_param ?? "");
  const [body, setBody] = useState<string[]>(scenario?.body_params ?? []);
  const [buttons, setButtons] = useState<Record<string, string>>(scenario?.button_params ?? {});
  const [enabled, setEnabled] = useState(scenario?.enabled ?? true);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [pending, start] = useTransition();

  const template = templates.find((t) => String(t.id) === templateId);
  const items = templates.map((t) => ({
    value: String(t.id),
    label: `${t.name} (${t.language})${t.status === "approved" ? "" : ` · ${t.status}`}`,
  }));
  const bodyCount = template?.body_variables ?? 0;
  const urlButtons = template?.url_buttons_with_variable ?? [];
  const bodyValues = Array.from({ length: bodyCount }, (_, i) => body[i] ?? "");
  const fields = fieldsIn(
    recipient,
    template?.header_has_variable ? header : "",
    ...bodyValues,
    ...urlButtons.map((i) => buttons[String(i)] ?? ""),
  );
  const locked = readOnly || pending;

  function setBodyValue(i: number, value: string) {
    setBody((prev) => {
      const next = Array.from({ length: Math.max(prev.length, bodyCount) }, (_, j) => prev[j] ?? "");
      next[i] = value;
      return next;
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(undefined);
    setSaved(false);
    start(async () => {
      const res = await saveScenario(scenario?.id ?? null, {
        code: code.trim().toUpperCase(),
        name: name.trim(),
        template_id: Number(templateId ?? 0),
        recipient,
        header_param: template?.header_has_variable ? header : null,
        body_params: bodyValues,
        button_params: Object.fromEntries(urlButtons.map((i) => [String(i), buttons[String(i)] ?? ""])),
        enabled,
      });
      if (res?.error) setError(res.error);
      else setSaved(true);
    });
  }

  return (
    <form onSubmit={submit} className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <div className="grid gap-6">
        {error && (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {saved && (
          <Alert>
            <CheckCircle2 />
            <AlertDescription>Saved.</AlertDescription>
          </Alert>
        )}
        <div className="grid gap-5 sm:grid-cols-2 sm:items-start">
          <div className="grid gap-2">
            <Label htmlFor="code">Code</Label>
            <Input
              id="code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))}
              placeholder="ORDER_SHIPPED"
              maxLength={40}
              disabled={locked}
              required
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">IFS sends this code to pick the scenario.</p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Order shipped"
              maxLength={100}
              disabled={locked}
              required
            />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="template">Template</Label>
          <Select items={items} value={templateId} onValueChange={setTemplateId} disabled={locked}>
            <SelectTrigger id="template" className="w-full">
              <SelectValue placeholder="Pick a template" />
            </SelectTrigger>
            <SelectContent>
              {items.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {template && template.status !== "approved" && (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              WhatsApp hasn&apos;t approved this template yet. You can set up the scenario now; sending works once
              it&apos;s approved.
            </p>
          )}
        </div>

        <fieldset className="grid gap-4 rounded-lg border p-4" disabled={locked}>
          <legend className="px-1 text-sm font-medium">Fill it from IFS</legend>
          <p className="text-sm text-muted-foreground">
            Write <code className="font-mono">{"{name}"}</code> for a value IFS sends, mixed with any text. A dot reads
            inside an object: <code className="font-mono">{"{customer.name}"}</code>.
          </p>
          <Row label="Send to" hint="A phone number. Local numbers use the default country code (Overview).">
            <Input value={recipient} onChange={(e) => setRecipient(e.target.value)} aria-label="Send to" required />
          </Row>
          {template?.header_has_variable && (
            <Row label={<>Header <code className="font-mono">{"{{1}}"}</code></>}>
              <Input value={header} onChange={(e) => setHeader(e.target.value)} aria-label="Header variable" />
            </Row>
          )}
          {bodyValues.map((value, i) => (
            <Row key={i} label={<code className="font-mono">{`{{${i + 1}}}`}</code>}>
              <Input
                value={value}
                onChange={(e) => setBodyValue(i, e.target.value)}
                aria-label={`Variable ${i + 1}`}
                placeholder={`{field${i + 1}}`}
              />
            </Row>
          ))}
          {urlButtons.map((i) => (
            <Row key={`b${i}`} label={<>Button &ldquo;{template?.buttons[i]?.text}&rdquo;</>}>
              <Input
                value={buttons[String(i)] ?? ""}
                onChange={(e) => setButtons((b) => ({ ...b, [String(i)]: e.target.value }))}
                aria-label={`Button ${i + 1} variable`}
              />
            </Row>
          ))}
          {!template && <p className="text-sm text-muted-foreground">Pick a template to see its variables.</p>}
        </fieldset>

        <label className="flex items-center gap-3 text-sm">
          <Switch checked={enabled} onCheckedChange={setEnabled} disabled={locked} />
          <span>
            <span className="font-medium">On.</span>{" "}
            <span className="text-muted-foreground">While off, AtroNexus refuses this scenario from IFS.</span>
          </span>
        </label>

        {fields.length > 0 && (
          <div className="grid gap-2">
            <span className="text-sm font-medium">Call it from IFS</span>
            <pre className="overflow-x-auto rounded-lg border bg-muted/50 p-3 font-mono text-xs leading-relaxed">
              {"BEGIN\n   " + plsqlCall(code, fields).replace(/\n/g, "\n   ") + "\nEND;"}
            </pre>
            <p className="text-xs text-muted-foreground">
              IFS must send: {fields.map((f) => <code key={f} className="mr-1.5 font-mono">{f}</code>)}. Replace the
              &amp;ATTRIBUTES with your event&apos;s own.
            </p>
          </div>
        )}

        {!readOnly && (
          <div>
            <Button type="submit" disabled={pending}>
              {pending && <Loader2 className="animate-spin" />}
              {scenario ? "Save" : "Create scenario"}
            </Button>
          </div>
        )}
      </div>

      {template && (
        <div className="grid gap-2 lg:sticky lg:top-4">
          <span className="text-sm font-medium">What gets sent</span>
          <TemplatePreview
            header={template.header_text}
            body={template.body_text}
            footer={template.footer_text}
            buttons={template.buttons}
            bodyExamples={bodyValues}
            headerExample={header}
          />
        </div>
      )}
    </form>
  );
}
