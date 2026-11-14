import { Badge } from "@/components/ui/badge";

const STATUS: Record<string, { label: string; variant: "secondary" | "outline" | "destructive" | "default" }> = {
  draft: { label: "Draft", variant: "outline" },
  pending: { label: "In review", variant: "outline" },
  approved: { label: "Approved", variant: "secondary" },
  rejected: { label: "Rejected", variant: "destructive" },
  paused: { label: "Paused", variant: "destructive" },
  disabled: { label: "Disabled", variant: "destructive" },
};

/** A template's WhatsApp review status. */
export function TemplateStatus({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}
