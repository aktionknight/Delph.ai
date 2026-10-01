/** Same-origin API gateway. Cookies and binary/SSE bodies pass through intact. */
type Environment = Record<string, string | undefined>;
const HOP_HEADERS = ["connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"];

function backendOrigin(env: Environment): string {
  const configured = env.BACKEND_URL?.trim() || env.BACKEND_URL_PRODUCTION?.trim() || env.NEXT_PUBLIC_API_URL?.trim();
  if (!configured && env.NODE_ENV === "production") {
    throw new Error("Set BACKEND_URL in Vercel to the Render backend origin, then redeploy.");
  }
  let url: URL;
  try { url = new URL(configured || "http://127.0.0.1:8000"); }
  catch { throw new Error("BACKEND_URL must be a valid HTTP or HTTPS backend origin."); }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("BACKEND_URL must be the backend origin only, without /api, a path, or query parameters.");
  }
  return url.origin;
}

function filteredHeaders(source: Headers): Headers {
  const headers = new Headers(source);
  const connectionNames = (source.get("connection") || "").split(",").map((name) => name.trim()).filter(Boolean);
  for (const name of [...HOP_HEADERS, ...connectionNames]) headers.delete(name);
  return headers;
}

function errorResponse(detail: string, status: number): Response {
  return Response.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function forwardApiRequest(request: Request, env: Environment, send: typeof fetch = fetch): Promise<Response> {
  let origin: string;
  try { origin = backendOrigin(env); }
  catch (error) { return errorResponse((error as Error).message, 503); }
  const incoming = new URL(request.url);
  if (!incoming.pathname.startsWith("/api/")) return errorResponse("API route not found.", 404);
  const target = `${origin}${incoming.pathname.slice(4)}${incoming.search}`;
  const headers = filteredHeaders(request.headers);
  for (const name of ["forwarded", "x-forwarded-host", "x-forwarded-proto", "x-forwarded-for"]) headers.delete(name);
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method, headers, cache: "no-store", redirect: "manual",
    signal: AbortSignal.timeout(270_000),
  };
  if (!["GET", "HEAD"].includes(request.method) && request.body) {
    init.body = request.body;
    init.duplex = "half";
  }
  try {
    const upstream = await send(target, init);
    const outgoing = filteredHeaders(upstream.headers);
    outgoing.delete("content-encoding");
    const cookies = upstream.headers.getSetCookie();
    outgoing.delete("set-cookie");
    for (const cookie of cookies) outgoing.append("set-cookie", cookie);
    return new Response(request.method === "HEAD" || [204, 205, 304].includes(upstream.status) ? null : upstream.body, {
      status: upstream.status, statusText: upstream.statusText, headers: outgoing,
    });
  } catch {
    return errorResponse("Cannot reach the backend API. Check BACKEND_URL and the Render service health, then retry.", 502);
  }
}

export async function proxyRequest(request: Request): Promise<Response> {
  return forwardApiRequest(request, process.env);
}
