import type { SentMessageOut } from "@/api/generated/models";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const STATUS: Record<string, { label: string; variant: "secondary" | "outline" | "destructive" | "default" }> = {
  sending: { label: "Sending", variant: "outline" },
  sent: { label: "Sent", variant: "outline" },
  delivered: { label: "Delivered", variant: "secondary" },
  read: { label: "Read", variant: "default" },
  failed: { label: "Failed", variant: "destructive" },
};

function when(value?: string | null): string {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "—";
}

/** "+94771234567" -> "+94 77 123 4567"-ish grouping is country-specific; just add the plus. */
function phone(value: string): string {
  return `+${value}`;
}

export function MessagesTable({ messages }: { messages: SentMessageOut[] }) {
  if (messages.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No messages yet. They appear here when IFS sends one, or when you send a test.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="py-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Sent</TableHead>
            <TableHead>Scenario</TableHead>
            <TableHead>To</TableHead>
            <TableHead>Message</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {messages.map((m) => {
            const status = STATUS[m.status] ?? { label: m.status, variant: "outline" as const };
            return (
              <TableRow key={m.id}>
                <TableCell className="text-muted-foreground">{when(m.created_at)}</TableCell>
                <TableCell>
                  <div className="grid">
                    <span className="font-mono text-xs">{m.scenario_code ?? "—"}</span>
                    <span className="text-xs text-muted-foreground">
                      {m.source === "test" ? "Test" : "From IFS"} · {m.template_name}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs whitespace-nowrap">{phone(m.to_phone)}</TableCell>
                <TableCell>
                  <p className="line-clamp-2 max-w-80 text-sm whitespace-pre-line">{m.text}</p>
                </TableCell>
                <TableCell>
                  <div className="grid gap-1">
                    <Badge variant={status.variant}>{status.label}</Badge>
                    {m.error && <span className="max-w-56 text-xs text-destructive">{m.error}</span>}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
