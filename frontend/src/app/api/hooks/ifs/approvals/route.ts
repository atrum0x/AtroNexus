import { backendHeaders, backendUrl } from "@/api/fetcher";

// IFS (the customer's IFS Connect routing address) posts approval requests
// here. The backend only accepts calls carrying the internal key, so this
// forwards the request with it. IFS authenticates with
// "Authorization: Bearer <hook key>", which the backend checks.

const MAX_BODY = 512 * 1024;

export async function POST(req: Request): Promise<Response> {
  const body = await req.text();
  if (body.length > MAX_BODY) {
    return Response.json({ detail: "Message too large." }, { status: 413 });
  }
  const res = await fetch(backendUrl("/api/hooks/ifs/approvals"), {
    method: "POST",
    headers: {
      ...backendHeaders(),
      "Content-Type": "application/json",
      Authorization: req.headers.get("authorization") ?? "",
    },
    body,
    cache: "no-store",
  });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}
