export type Source = { id: string; name: string; text: string; source_type: string };
export type Brand = { id: string; name: string; description: string; voice: string; approved_claims: string[]; forbidden_phrases: string[]; sources: Source[] };
export type Strategy = { positioning: string; core_message: string; audience_summary: string; content_pillars: string[]; assumptions: string[]; creative_directions: { id: string; name: string; description: string; rationale: string }[]; source_refs: string[] };
export type Version = { version: number; hook: string; body: string; cta: string; source_refs: string[]; evaluation: { passed: boolean; issues: string[]; checks: Record<string, boolean> }; created_at: string };
export type Asset = { id: string; campaign_id: string; platform: string; asset_type: string; status: string; current_version: number; versions: Version[]; approvals: { version: number; decision: string; feedback: string; created_at: string }[] };
export type Trace = { id: string; event_type: string; message: string; status: string; timestamp: string };
export type Campaign = { id: string; brand_id: string; name: string; brief: string; goal: string; audience: string; platforms: string[]; duration_days: number; status: string; created_at: string; strategy: Strategy | null; selected_direction: string | null; timeline: { id: string; day: number; stage: string; platform: string; asset_type: string; objective: string }[]; assets: Asset[]; trace: Trace[]; experiments: { id: string; name: string; asset_id: string; variable: string; variants: { label: string; hook: string; impressions: number; clicks: number; conversions: number }[]; is_demo: boolean }[]; learnings: { id: string; statement: string; evidence: string; confidence: number; saved_to_brand: boolean }[] };
export type Analytics = { is_demo: boolean; impressions: number; clicks: number; conversions: number; ctr: number; platforms: { platform: string; impressions: number; clicks: number; conversions: number }[]; observations: string[] };

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
