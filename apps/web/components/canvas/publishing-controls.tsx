"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, type Asset, type Campaign, type ConnectionResponse } from "@/lib/api";
import { Badge, ErrorNotice } from "@/components/ui";
import type { Action } from "@/components/campaign/workspace";

export function PublishingControls({ asset, campaign, busy, dirty, action }: { asset: Asset; campaign?: Campaign; busy: boolean; dirty: boolean; action: Action }) {
  const [when, setWhen] = useState("");
  const supported = ["x", "linkedin"].includes(asset.platform);
  const live = campaign?.generation_mode === "gemini";
  const query = useQuery({ queryKey: ["connections", campaign?.brand_id], queryFn: () => api<ConnectionResponse>(`/connections?brand_id=${encodeURIComponent(campaign!.brand_id)}`), enabled: !!campaign && live && supported });
  const connection = query.data?.connections.find((c) => c.platform === asset.platform && c.status === "active");
  const publication = asset.publication;
  const ready = ["approved", "publish_failed"].includes(asset.status);
  return <section className="panel"><h3>{ready ? "Ready to publish" : "Social publication"}</h3><ErrorNotice error={query.error} />
    {publication && <><Badge>{publication.status.replaceAll("_", " ")}</Badge><p className="small muted">Version {publication.version} · {publication.account_name} · {new Date(publication.run_at || publication.scheduled_at).toLocaleString()}</p>{publication.url && <a className="text-link" href={publication.url} target="_blank" rel="noreferrer">View published post</a>}{publication.error && <div className="notice">{publication.error}</div>}{publication.post_ids.length > 0 && <p className="small muted">{publication.post_ids.length} remote post receipts saved.</p>}</>}
    {!live && ready && <button className="button secondary full" disabled={busy || dirty} onClick={() => action(`/assets/${asset.id}/publish`, { version: asset.current_version })}>Record demo publication</button>}
    {live && supported && ready && <>{connection ? <><p className="small muted">Posts publicly to {connection.display_name}. The exact approved copy and reviewed static are sent.</p><button className="button primary full" disabled={busy || dirty} onClick={() => action(`/assets/${asset.id}/social-publish`, { version: asset.current_version, connection_id: connection.id })}>Publish now</button>
      <label>Schedule date and time (your local timezone)<input type="datetime-local" value={when} disabled={busy || dirty} onChange={(e) => setWhen(e.target.value)} /></label><button className="button secondary full" disabled={busy || dirty || !when || new Date(when).getTime() <= Date.now()} onClick={() => action(`/assets/${asset.id}/schedule`, { version: asset.current_version, connection_id: connection.id, scheduled_at: new Date(when).toISOString() })}>Schedule post</button></> : <Link href="/settings/integrations" className="button secondary full">Connect {asset.platform === "x" ? "X" : "LinkedIn"}</Link>}</>}
    {asset.status === "scheduled" && <button className="button secondary full" disabled={busy} onClick={() => action(`/assets/${asset.id}/cancel-publication`)}>Cancel scheduled post</button>}
    {asset.status === "publish_unknown" && <p className="small muted">Inspect the social account before retrying. Automatic replay is blocked because the request may have posted.</p>}
    {live && !supported && <p className="small muted">Live Instagram publishing is not enabled.</p>}
    <p className="small muted">Revisions cancel queued publication and require fresh approval. Scheduled posts need the publishing worker running.</p>
  </section>;
}
