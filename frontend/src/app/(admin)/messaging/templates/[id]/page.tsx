import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getMessageTemplate } from "@/api/generated/endpoints/messaging/messaging";
import { DeleteButton } from "@/components/delete-button";
import { PageHeader, TableSkeleton } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth";
import { canManage } from "@/lib/roles";

import { removeTemplate } from "../../actions";
import { RefreshButton } from "../refresh-button";
import { TemplateStatus } from "../status-badge";
import { TemplateForm } from "../template-form";
import { TemplatePreview } from "../template-preview";

export default function TemplatePage({ params }: PageProps<"/messaging/templates/[id]">) {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <Template params={params} />
    </Suspense>
  );
}

const STATUS_TEXT: Record<string, string> = {
  draft: "Not with WhatsApp yet. Fix what's below and submit again.",
  pending: "WhatsApp is reviewing it. That usually takes minutes, sometimes up to a day; the status updates by itself.",
  approved: "Approved by WhatsApp. Scenarios using it can send.",
  rejected: "WhatsApp rejected it. Make a new template with the problem fixed.",
  paused: "WhatsApp paused it because people reported or blocked these messages. Sending fails until it's back.",
  disabled: "WhatsApp disabled it. Make a new template.",
};

async function Template({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();
  let data;
  try {
    data = await Promise.all([getMessageTemplate(id), getCurrentUser()]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  const [t, user] = data;
  const manager = canManage(user);
  const examples = t.examples as { body?: string[]; header?: string | null };

  return (
    <div className="grid gap-6">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {t.name}
            <TemplateStatus status={t.status} />
          </span>
        }
        back={{ href: "/messaging/templates", label: "Templates" }}
        description={`${t.language} · ${t.category.toLowerCase()} · used by ${t.used_by} scenario${t.used_by === 1 ? "" : "s"}`}
      />

      <Alert variant={["rejected", "paused", "disabled"].includes(t.status) ? "destructive" : "default"} className="max-w-3xl">
        <AlertTitle>{STATUS_TEXT[t.status] ?? t.status}</AlertTitle>
        {t.status_reason && <AlertDescription>{t.status_reason}</AlertDescription>}
      </Alert>

      {t.status === "draft" && manager ? (
        <TemplateForm template={t} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)] lg:items-start">
          <TemplatePreview
            header={t.header_text}
            body={t.body_text}
            footer={t.footer_text}
            buttons={t.buttons}
            bodyExamples={examples.body ?? []}
            headerExample={examples.header}
          />
          <Card>
            <CardHeader>
              <CardTitle>Variables</CardTitle>
              <CardDescription>Scenarios fill these with values from IFS.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-1.5 text-sm">
              <p>
                Message: <span className="font-medium">{t.body_variables}</span>
                {t.header_has_variable && <> · header: 1</>}
                {t.url_buttons_with_variable.length > 0 && <> · link buttons: {t.url_buttons_with_variable.length}</>}
              </p>
              <p className="text-muted-foreground">
                Name in WhatsApp: <code className="font-mono text-xs">{t.meta_name}</code>
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {manager && (
        <div className="flex flex-wrap items-start gap-6">
          {t.status !== "draft" && <RefreshButton id={t.id} label="Check status now" />}
          <DeleteButton
            action={removeTemplate.bind(null, t.id)}
            title={`Delete ${t.name}?`}
            description="It's removed from WhatsApp too. Scenarios can't use a deleted template, so delete or change those first."
          />
        </div>
      )}
    </div>
  );
}
