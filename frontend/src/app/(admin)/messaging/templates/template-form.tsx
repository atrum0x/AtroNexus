"use client";

import { AlertCircle, Loader2, Plus, Send, X } from "lucide-react";
import { useState, useTransition } from "react";

import type { TemplateOut } from "@/api/generated/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { saveTemplate } from "../actions";
import { TemplatePreview, variableNumbers, type PreviewButton } from "./template-preview";

const CATEGORIES = [
  { value: "UTILITY", label: "Utility (updates about something the person did or asked for)" },
  { value: "MARKETING", label: "Marketing (offers, news)" },
];
const BUTTON_TYPES = [
  { value: "URL", label: "Link" },
  { value: "QUICK_REPLY", label: "Quick reply" },
];

type Button_ = { type: "URL" | "QUICK_REPLY"; text: string; url: string };

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor?: string; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** New template, or changing a draft. Shows a live preview with the example values. */
export function TemplateForm({ template }: { template?: TemplateOut }) {
  const examples = (template?.examples ?? {}) as { body?: string[]; header?: string | null; buttons?: Record<string, string> };
  const [name, setName] = useState(template?.name ?? "");
  const [language, setLanguage] = useState(template?.language ?? "en");
  const [category, setCategory] = useState<string | null>(template?.category ?? "UTILITY");
  const [header, setHeader] = useState(template?.header_text ?? "");
  const [body, setBody] = useState(template?.body_text ?? "");
  const [footer, setFooter] = useState(template?.footer_text ?? "");
  const [buttons, setButtons] = useState<Button_[]>(
    (template?.buttons ?? []).map((b) => ({ type: b.type, text: b.text, url: b.url ?? "" })),
  );
  const [bodyExamples, setBodyExamples] = useState<string[]>(examples.body ?? []);
  const [headerExample, setHeaderExample] = useState(examples.header ?? "");
  const [buttonExamples, setButtonExamples] = useState<Record<string, string>>(examples.buttons ?? {});
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();

  const bodyVars = variableNumbers(body);
  const headerHasVar = variableNumbers(header).length > 0;
  const examplesFor = (n: number) => bodyExamples[n - 1] ?? "";

  function setExample(n: number, value: string) {
    setBodyExamples((prev) => {
      const next = [...prev];
      while (next.length < n) next.push("");
      next[n - 1] = value;
      return next;
    });
  }

  function updateButton(i: number, change: Partial<Button_>) {
    setButtons((prev) => prev.map((b, j) => (j === i ? { ...b, ...change } : b)));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(undefined);
    const count = bodyVars.length ? Math.max(...bodyVars) : 0;
    start(async () => {
      const res = await saveTemplate(template?.id ?? null, {
        name: name.trim(),
        language: language.trim(),
        category: category === "MARKETING" ? "MARKETING" : "UTILITY",
        header_text: header.trim() || null,
        body_text: body,
        footer_text: footer.trim() || null,
        buttons: buttons.map((b) => ({ type: b.type, text: b.text.trim(), url: b.type === "URL" ? b.url.trim() : null })),
        body_examples: Array.from({ length: count }, (_, i) => bodyExamples[i] ?? ""),
        header_example: headerHasVar ? headerExample : null,
        button_examples: Object.fromEntries(
          buttons.flatMap((b, i) =>
            b.type === "URL" && variableNumbers(b.url).length ? [[String(i), buttonExamples[String(i)] ?? ""]] : [],
          ),
        ),
      });
      if (res?.error) setError(res.error);
    });
  }

  const previewButtons: PreviewButton[] = buttons.map((b) => ({ type: b.type, text: b.text, url: b.url }));

  return (
    <form onSubmit={submit} className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <div className="grid gap-5">
        {error && (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="grid gap-5 sm:grid-cols-2 sm:items-start">
          <Field label="Name" htmlFor="name" hint="Lowercase letters, digits and _. For example order_shipped.">
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
              maxLength={60}
              required
            />
          </Field>
          <Field label="Language" htmlFor="language" hint="A WhatsApp language code: en, en_US, si, ta ...">
            <Input id="language" value={language} onChange={(e) => setLanguage(e.target.value)} maxLength={10} required />
          </Field>
        </div>
        <Field label="Category" hint="WhatsApp prices and reviews them differently. Wrong ones get rejected or recategorized.">
          <Select items={CATEGORIES} value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Header (optional)" htmlFor="header" hint="Bold first line. Can have one variable, {{1}}.">
          <Input id="header" value={header} onChange={(e) => setHeader(e.target.value)} maxLength={60} />
        </Field>
        {headerHasVar && (
          <Field label="Example for the header's {{1}}" htmlFor="header_example">
            <Input id="header_example" value={headerExample} onChange={(e) => setHeaderExample(e.target.value)} />
          </Field>
        )}
        <Field
          label="Message"
          htmlFor="body"
          hint={
            <>
              Put <code className="font-mono">{"{{1}}"}</code>, <code className="font-mono">{"{{2}}"}</code>, ... where
              values from IFS go. Not at the very start or end. *bold* and _italic_ work.
            </>
          }
        >
          <Textarea id="body" value={body} onChange={(e) => setBody(e.target.value)} maxLength={1024} rows={5} required />
        </Field>
        {bodyVars.length > 0 && (
          <div className="grid gap-3 rounded-lg border p-4">
            <p className="text-sm">
              <span className="font-medium">Example values.</span>{" "}
              <span className="text-muted-foreground">WhatsApp reviews the message with these. Make them realistic.</span>
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {Array.from({ length: Math.max(...bodyVars) }, (_, i) => i + 1).map((n) => (
                <div key={n} className="flex items-center gap-2">
                  <code className="w-10 shrink-0 font-mono text-xs text-muted-foreground">{`{{${n}}}`}</code>
                  <Input
                    aria-label={`Example for {{${n}}}`}
                    value={examplesFor(n)}
                    onChange={(e) => setExample(n, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
        <Field label="Footer (optional)" htmlFor="footer" hint="Small grey text. No variables.">
          <Input id="footer" value={footer} onChange={(e) => setFooter(e.target.value)} maxLength={60} />
        </Field>

        <div className="grid gap-3">
          <div className="flex items-center justify-between gap-2">
            <Label>Buttons (optional)</Label>
            {buttons.length < 3 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setButtons((b) => [...b, { type: "URL", text: "", url: "https://" }])}
              >
                <Plus />
                Add button
              </Button>
            )}
          </div>
          {buttons.map((b, i) => (
            <div key={i} className="grid gap-3 rounded-lg border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  items={BUTTON_TYPES}
                  value={b.type}
                  onValueChange={(v) => updateButton(i, { type: v === "QUICK_REPLY" ? "QUICK_REPLY" : "URL" })}
                >
                  <SelectTrigger className="w-36" aria-label={`Button ${i + 1} type`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {BUTTON_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  className="min-w-0 flex-1"
                  aria-label={`Button ${i + 1} text`}
                  placeholder="Button text"
                  value={b.text}
                  maxLength={25}
                  onChange={(e) => updateButton(i, { text: e.target.value })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove button ${i + 1}`}
                  onClick={() => setButtons((all) => all.filter((_, j) => j !== i))}
                >
                  <X />
                </Button>
              </div>
              {b.type === "URL" && (
                <>
                  <Input
                    aria-label={`Button ${i + 1} address`}
                    placeholder="https://example.com/orders/{{1}}"
                    value={b.url}
                    onChange={(e) => updateButton(i, { url: e.target.value })}
                  />
                  {variableNumbers(b.url).length > 0 && (
                    <div className="flex items-center gap-2">
                      <code className="w-10 shrink-0 font-mono text-xs text-muted-foreground">{"{{1}}"}</code>
                      <Input
                        aria-label={`Example for button ${i + 1}`}
                        placeholder="Example value"
                        value={buttonExamples[String(i)] ?? ""}
                        onChange={(e) => setButtonExamples((ex) => ({ ...ex, [String(i)]: e.target.value }))}
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            A link may end with {"{{1}}"}, filled from IFS (for example an order number).
          </p>
        </div>

        <div>
          <Button type="submit" disabled={pending}>
            {pending ? <Loader2 className="animate-spin" /> : <Send />}
            {template ? "Submit again to WhatsApp" : "Submit to WhatsApp"}
          </Button>
        </div>
      </div>

      <div className="grid gap-2 lg:sticky lg:top-4">
        <span className="text-sm font-medium">Preview</span>
        <TemplatePreview
          header={header}
          body={body}
          footer={footer}
          buttons={previewButtons}
          bodyExamples={bodyExamples}
          headerExample={headerExample}
        />
      </div>
    </form>
  );
}
