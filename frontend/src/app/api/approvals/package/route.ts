import { backendHeaders, backendUrl } from "@/api/fetcher";
import { getSessionToken } from "@/lib/session";

// Downloads the IFS package for the signed-in user's organization. The
// session token is in an HttpOnly cookie, so the browser can't call the
// backend itself; this passes the zip through.

export async function GET(): Promise<Response> {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Sign in first." }, { status: 401 });
  }
  const res = await fetch(backendUrl("/api/approvals/package"), {
    headers: { ...backendHeaders(), Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    return new Response(await res.text(), {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  }
  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition":
        res.headers.get("content-disposition") ?? 'attachment; filename="atronexus-approvals-ifs-package.zip"',
      "Cache-Control": "no-store",
    },
  });
}
