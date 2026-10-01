import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../lib/server/api-proxy.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { forwardApiRequest } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const production = { NODE_ENV: "production", NEXT_PUBLIC_API_URL: "https://backend.example/" };

test("production legacy setting routes /api paths and preserves query/cookies", async () => {
  const request = new Request("https://frontend.example/api/campaigns/123/export?format=pdf", { headers: { cookie: "launchpad_session=fixture", host: "wrong-host", origin: "https://frontend.example" } });
  const response = await forwardApiRequest(request, production, async (target, init) => {
    assert.equal(target, "https://backend.example/campaigns/123/export?format=pdf");
    assert.equal(init.headers.get("cookie"), "launchpad_session=fixture");
    assert.equal(init.headers.get("origin"), "https://frontend.example");
    assert.equal(init.headers.has("host"), false);
    assert.equal(init.redirect, "manual");
    return Response.json({ ok: true });
  });
  assert.equal(response.status, 200);
});

test("server BACKEND_URL takes precedence", async () => {
  await forwardApiRequest(new Request("https://frontend.example/api/health"), { ...production, BACKEND_URL: " https://render.example/ " }, async (target) => {
    assert.equal(target, "https://render.example/health");
    return Response.json({ status: "ok" });
  });
});

test("missing production configuration is actionable and never tries localhost", async () => {
  const response = await forwardApiRequest(new Request("https://frontend.example/api/health"), { NODE_ENV: "production" }, () => assert.fail("No network request expected"));
  assert.equal(response.status, 503);
  assert.match((await response.json()).detail, /BACKEND_URL/);
});

test("origin-only configuration rejects malformed targets", async () => {
  for (const target of ["https://backend.example/api", "https://user:secret@backend.example", "file:///tmp/backend", "https://backend.example?token=1"]) {
    const response = await forwardApiRequest(new Request("https://frontend.example/api/health"), { NODE_ENV: "production", BACKEND_URL: target }, () => assert.fail("No network request expected"));
    assert.equal(response.status, 503);
  }
});

test("binary PDF/ZIP/media bytes pass through unchanged", async () => {
  const bytes = new Uint8Array([0, 255, 128, 13, 10, 37, 80, 68, 70]);
  const response = await forwardApiRequest(new Request("https://frontend.example/api/export"), production, async () => new Response(bytes, { headers: { "content-type": "application/pdf", "content-disposition": 'attachment; filename="campaign.pdf"', "content-length": "999", "content-encoding": "gzip" } }));
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
  assert.equal(response.headers.get("content-disposition"), 'attachment; filename="campaign.pdf"');
  assert.equal(response.headers.has("content-length"), false);
  assert.equal(response.headers.has("content-encoding"), false);
});

test("multipart upload is forwarded as original bytes", async () => {
  const bytes = new Uint8Array([45, 45, 98, 13, 10, 0, 255, 128]);
  const request = new Request("https://frontend.example/api/sources/upload", { method: "POST", body: bytes, headers: { "content-type": "multipart/form-data; boundary=b" } });
  await forwardApiRequest(request, production, async (target, init) => {
    assert.deepEqual(new Uint8Array(await new Response(init.body).arrayBuffer()), bytes);
    assert.equal(init.headers.get("content-type"), "multipart/form-data; boundary=b");
    assert.equal(init.duplex, "half");
    return Response.json({ ok: true });
  });
});

test("authentication set-cookie headers are retained separately", async () => {
  const headers = new Headers();
  headers.append("set-cookie", "launchpad_session=fixture; HttpOnly; Secure; SameSite=Strict; Path=/");
  headers.append("set-cookie", "other=fixture; Path=/");
  const response = await forwardApiRequest(new Request("https://frontend.example/api/auth/login"), production, async () => new Response("{}", { headers }));
  assert.equal(response.headers.getSetCookie().length, 2);
  assert.match(response.headers.getSetCookie()[0], /HttpOnly/);
});

test("SSE response streams before the entire upstream response completes", async () => {
  let controller;
  const body = new ReadableStream({ start(value) { controller = value; value.enqueue(new TextEncoder().encode("data: started\n\n")); } });
  const response = await forwardApiRequest(new Request("https://frontend.example/api/jobs/1/stream"), production, async () => new Response(body, { headers: { "content-type": "text/event-stream" } }));
  const reader = response.body.getReader();
  assert.equal(new TextDecoder().decode((await reader.read()).value), "data: started\n\n");
  controller.close();
  assert.equal((await reader.read()).done, true);
});

test("upstream failures preserve status; network failures produce a safe 502", async () => {
  const response = await forwardApiRequest(new Request("https://frontend.example/api/me"), production, async () => Response.json({ detail: "Sign in" }, { status: 401 }));
  assert.equal(response.status, 401);
  const offline = await forwardApiRequest(new Request("https://frontend.example/api/me"), production, async () => { throw new Error("secret internals"); });
  assert.equal(offline.status, 502);
  assert.doesNotMatch(await offline.text(), /secret internals/);
});

test("HEAD/204 responses have no body and unsafe proxy headers are removed", async () => {
  const response = await forwardApiRequest(new Request("https://frontend.example/api/health", { method: "HEAD", headers: { connection: "x-private", "x-private": "secret", "x-forwarded-host": "attacker.example" } }), production, async (_, init) => {
    assert.equal(init.headers.has("x-private"), false);
    assert.equal(init.headers.has("x-forwarded-host"), false);
    return new Response("ignored", { status: 200 });
  });
  assert.equal(await response.text(), "");
});
