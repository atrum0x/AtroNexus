import { backendHeaders, backendUrl } from "@/api/fetcher";

// Meta's WhatsApp webhook: template review results and delivery reports.
// Set this URL (https://<app>/api/hooks/meta/whatsapp) in the Meta app. The
// backend only accepts calls carrying the internal key, so this forwards
// them with it. Meta signs each POST (X-Hub-Signature-256) over the exact
// bytes, so the body is passed on untouched for the backend to check.

const PATH = "/api/hooks/meta/whatsapp";
const MAX_BODY = 1024 * 1024;

async function relay(res: Response): Promise<Response> {
  return new Response(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}

// Meta calls this once to verify the webhook (hub.mode, hub.verify_token, hub.challenge).
export async function GET(req: Request): Promise<Response> {
  const query = new URL(req.url).search;
  const res = await fetch(backendUrl(PATH + query), { headers: backendHeaders(), cache: "no-store" });
  return relay(res);
}

export async function POST(req: Request): Promise<Response> {
  const body = await req.arrayBuffer();
  if (body.byteLength > MAX_BODY) {
    return Response.json({ detail: "Too large." }, { status: 413 });
  }
  const res = await fetch(backendUrl(PATH), {
    method: "POST",
    headers: {
      ...backendHeaders(),
      "Content-Type": "application/json",
      "X-Hub-Signature-256": req.headers.get("x-hub-signature-256") ?? "",
    },
    body,
    cache: "no-store",
  });
  return relay(res);
}
