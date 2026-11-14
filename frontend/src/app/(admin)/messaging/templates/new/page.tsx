import { PageHeader } from "@/components/page-header";

import { TemplateForm } from "../template-form";

export default function NewTemplatePage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="New template"
        back={{ href: "/messaging/templates", label: "Templates" }}
        description="Write the message once; scenarios fill its variables with values from IFS."
      />
      <TemplateForm />
    </div>
  );
}
