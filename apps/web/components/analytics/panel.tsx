"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api, title, type Analytics, type Campaign } from "@/lib/api";
import { Badge, ErrorNotice, Loading } from "@/components/ui";
import { SectionPrompt, SectionReview, savedPrompt } from "@/components/campaign/section-controls";
import type { Action } from "@/components/campaign/workspace";

export function AnalyticsPanel({ id, campaign, action, busy }: { id: string; campaign: Campaign; action: Action; busy: boolean }) {
  const [prompt, setPrompt] = useState(savedPrompt(campaign, "insights"));
  const query = useQuery({ queryKey: ["analytics", id], queryFn: () => api<Analytics>(`/campaigns/${id}/analytics`), refetchInterval: 60000 });
  if (query.isPending) return <Loading />;
  if (!query.data) return <><ErrorNotice error={query.error} /><button className="button secondary" onClick={() => void query.refetch()}>Retry analytics</button></>;
  const analytics = query.data;
  const provenance = analytics.is_demo ? "Simulated metrics · not real performance" : analytics.metrics_source === "social_api" ? "Live social API snapshots" : analytics.metrics_source === "mixed" ? "Social API + manual imports" : analytics.metrics_source === "none" ? "No measured results" : "Manually imported metrics";
  const unavailable = (key: string) => analytics.availability?.[key] === false;
  const max = Math.max(1, ...analytics.platforms.map((item) => item.impressions));
  return <><div className="section-heading"><div><h2>Make room for what you learn.</h2><p className="muted">Explore recorded campaign performance.</p></div><Badge tone="amber">{provenance}</Badge></div>
    {campaign.generation_mode === "gemini" && <button className="button secondary" disabled={busy} onClick={() => action(`/campaigns/${id}/sync-social-metrics`)}>Refresh social metrics and insights</button>}
    {analytics.sync && <><p className="small muted">Last social refresh: {new Date(analytics.sync.captured_at).toLocaleString()}</p>{analytics.sync.results.filter((r) => r.status === "unavailable").map((r, i) => <div className="notice" key={`${r.asset_id}-${i}`}>{r.error}</div>)}</>}
    <div className="metric-grid">{[{ label: "Impressions", value: unavailable("impressions") ? "—" : analytics.impressions.toLocaleString() }, { label: "Clicks", value: unavailable("clicks") ? "—" : analytics.clicks.toLocaleString() }, { label: "Conversions", value: unavailable("conversions") ? "—" : analytics.conversions.toLocaleString() }, { label: "Click-through rate", value: unavailable("clicks") || unavailable("impressions") ? "—" : `${(Number(analytics.ctr) * 100).toFixed(2)}%` }].map((metric) => <div className="metric-card" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><p>{metric.value === "—" ? "Unavailable from provider" : provenance}</p></div>)}</div>
    {analytics.metrics_source === "social_api" || analytics.metrics_source === "mixed" ? <p>{unavailable("likes") ? "Unknown" : analytics.likes} reactions · {unavailable("comments") ? "Unknown" : analytics.comments} comments · {unavailable("reposts") ? "Unknown" : analytics.reposts} reposts</p> : null}
    <div className="analytics-layout"><section className="panel"><h3>Impressions by platform</h3><p className="small muted">{analytics.is_demo ? "Deterministic simulation" : "Recorded metrics"}</p><div className="bar-chart">{analytics.platforms.map((platform) => <div key={platform.platform}><div className="row"><span>{title(platform.platform)}</span><strong>{platform.impressions.toLocaleString()}</strong></div><div className="bar-track"><span style={{ width: `${platform.impressions / max * 100}%` }} /></div><p className="small muted">{platform.clicks} clicks · {platform.conversions} conversions</p></div>)}</div></section>
      <section className="panel observations"><Sparkles size={22} /><h3>What the numbers suggest</h3>
        <SectionPrompt section="insights" value={prompt} onChange={setPrompt} busy={busy}
          generateLabel={campaign.generation_mode === "gemini" ? "Analyze with AI" : "Generate demo insights"} onGenerate={() => action(`/campaigns/${id}/insights`, { prompt })} />
        {campaign.insights?.map((insight, index) => <p key={`ai-${index}`}>{insight}</p>)}{analytics.observations.map((observation, index) => <p key={index}>{observation}</p>)}
        <span className="small muted">Observations are hypotheses. API snapshots report cumulative performance; unavailable data is unknown and does not establish causal lift.</span>
        <SectionReview campaign={campaign} section="insights" action={action} busy={busy} />
      </section></div>
  </>;
}
