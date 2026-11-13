import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";

import { ConnectionForm } from "../connection-form";

export default function NewConnectionPage() {
  return (
    <div className="grid max-w-2xl gap-6">
      <PageHeader
        title="New IFS connection"
        description="Use a dedicated IFS service user, with access only to what the tools need."
        back={{ href: "/connections", label: "IFS connections" }}
      />
      <Card>
        <CardContent>
          <ConnectionForm />
        </CardContent>
      </Card>
    </div>
  );
}
