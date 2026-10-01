import type { Asset } from "../../../packages/shared-types";
export type * from "../../../packages/shared-types";

export async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body && !isForm ? { "Content-Type": "application/json" } : undefined,
      body: body ? isForm ? body : JSON.stringify(body) : undefined,
      cache: "no-store"
    });
  } catch {
    throw new Error("Cannot reach the API. Check that the backend is running, then retry.");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail = error?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((issue: { loc?: string[]; msg?: string }) => `${issue.loc?.slice(1).join(" ") || "Input"}: ${issue.msg}`).join(". ")
      : `Request failed (${response.status}). Check the API connection and retry.`);
  }
  return response.json();
}

export function title(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
export function currentVersion(asset: Asset) { return asset.versions.find((version) => version.version === asset.current_version)!; }
export const platforms = [{ id: "linkedin", name: "LinkedIn", type: "post" }, { id: "instagram", name: "Instagram", type: "reel" }, { id: "x", name: "X", type: "thread" }];
