import { ExternalLink } from "lucide-react";

import type { CaptureOut } from "@/api/generated/models";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const LOCATION_LABEL: Record<string, string> = {
  captured: "Captured",
  denied: "Denied",
  unavailable: "Unavailable",
};

export function CapturesTable({
  captures,
  showTarget = true,
}: {
  captures: CaptureOut[];
  showTarget?: boolean;
}) {
  if (captures.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No captures yet. They show up here when someone opens a capture link from IFS.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="py-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            {showTarget && <TableHead>Capture page</TableHead>}
            <TableHead>Request ID</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>IP / device</TableHead>
            <TableHead>IFS</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {captures.map((c) => (
            <TableRow key={c.id} className="align-top">
              <TableCell className="whitespace-nowrap text-muted-foreground">
                {formatTime(c.captured_at)}
              </TableCell>
              {showTarget && <TableCell>{c.target_name}</TableCell>}
              <TableCell className="font-mono text-xs">{c.request_id}</TableCell>
              <TableCell>
                {c.status === "captured" && c.latitude != null && c.longitude != null ? (
                  <a
                    href={`https://www.openstreetmap.org/?mlat=${c.latitude}&mlon=${c.longitude}#map=17/${c.latitude}/${c.longitude}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-xs hover:underline"
                  >
                    {c.latitude.toFixed(5)}, {c.longitude.toFixed(5)}
                    <ExternalLink className="size-3" />
                  </a>
                ) : (
                  <Badge variant="outline">{LOCATION_LABEL[c.status] ?? c.status}</Badge>
                )}
                {c.accuracy != null && (
                  <div className="text-xs text-muted-foreground">± {Math.round(c.accuracy)} m</div>
                )}
                {c.location_error && (
                  <div className="text-xs text-muted-foreground">{c.location_error}</div>
                )}
              </TableCell>
              <TableCell className="text-xs">
                <div className="font-mono">{c.ip ?? "—"}</div>
                <div className="text-muted-foreground">
                  {[c.platform, c.screen].filter(Boolean).join(", ") || "—"}
                </div>
              </TableCell>
              <TableCell className="max-w-64">
                {c.writeback_status === "sent" ? (
                  <Badge className="bg-emerald-600 text-white dark:bg-emerald-500">Sent</Badge>
                ) : c.writeback_status === "failed" ? (
                  <>
                    <Badge variant="destructive">Failed</Badge>
                    <div className="mt-1 text-xs whitespace-normal text-destructive">
                      {c.writeback_error}
                    </div>
                  </>
                ) : (
                  <Badge variant="secondary">Sending</Badge>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function formatTime(iso: string) {
  // SQLite returns times without a zone; they're stored in UTC.
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  return date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) + " UTC";
}
