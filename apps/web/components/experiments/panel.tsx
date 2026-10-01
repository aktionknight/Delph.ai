"use client";

import { useState } from "react";
import { FlaskConical } from "lucide-react";
import { currentVersion, title, type Campaign } from "@/lib/api";
import { Badge, Empty } from "@/components/ui";
import type { Action } from "@/components/campaign/workspace";

export function ExperimentsPanel({ campaign, action, busy }: { campaign: Campaign; action: Action; busy: boolean }) {
  const eligible = campaign.assets.filter((asset) => ["approved", "published"].includes(asset.status));
  const [assetId, setAssetId] = useState(eligible[0]?.id || "");
  const [prompt, setPrompt] = useState("");
  const selected = eligible.find((asset) => asset.id === assetId);
  return <>
    <div className="section-heading"><div><h2>A better hook starts with a question.</h2><p className="muted">Compare hook variants against recorded evidence.</p></div><Badge tone="amber">{campaign.generation_mode === "gemini" ? "Draft variants · import results" : "Simulated metrics"}</Badge></div>
    <div className="notice">Variants require their own asset evaluation and human approval before publication. Demo results are simulated; AI experiments start without results.</div>
    <div className="panel">
      <div className="generation-bar"><label>Approved source asset<select disabled={busy} value={selected?.id || ""} onChange={(event) => { setAssetId(event.target.value); setPrompt(""); }}><option value="">Select an approved asset</option>{eligible.map((asset) => <option key={asset.id} value={asset.id}>{title(asset.platform)} · {currentVersion(asset).hook.slice(0, 70)}</option>)}</select></label>
        <button className="button primary" disabled={busy || !selected} onClick={() => action(`/campaigns/${campaign.id}/experiments`, { asset_id: selected!.id, variable: "hook", prompt: prompt.trim() || undefined })}><FlaskConical size={16} /> Create hook experiment</button>
      </div>
      <label>Custom experiment instructions<textarea rows={3} maxLength={2000} value={prompt} disabled={busy} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the hook approaches to compare, such as a practical question versus a benefit statement." /></label>
      <p className="small muted">Variants retain the source deliverable's timeline and campaign context. Create reviewable assets below to fine tune each variant and approve its exact version.</p>
    </div>
    {!eligible.length && <p className="muted">Approve a passing content asset before creating an experiment.</p>}
    {!campaign.experiments.length ? <div className="panel"><Empty title="Turn a creative choice into a test.">Your experiments and recorded variant results will live here.</Empty></div> : campaign.experiments.map((experiment) => <section className="panel" key={experiment.id}>
      <div className="row"><h3>{experiment.name}</h3><Badge tone="amber">{experiment.is_demo ? "Simulated results" : "Manual results · unverified"}</Badge></div>
      <div className="variant-grid">{experiment.variants.map((variant, variantIndex) => <div className="variant-card" key={`${variant.label}-${variantIndex}`}>
        <span className="label">VARIANT {variant.label}</span><h3>{variant.hook}</h3>
        {variant.evaluation && <Badge tone={variant.evaluation.passed ? "green" : "red"}>{variant.evaluation.passed ? "Copy evaluation passed" : "Copy needs repair"}</Badge>}
        <button className="button secondary" disabled={busy || !!variant.review_asset_id} onClick={() => action(`/campaigns/${campaign.id}/experiments/${experiment.id}/variants/${variantIndex}/asset`)}>{variant.review_asset_id ? "Added to content canvas" : "Create reviewable asset"}</button>
        {!experiment.is_demo && <MetricForm campaignId={campaign.id} experimentId={experiment.id} label={variant.label} action={action} busy={busy} />}
        <div className="variant-stat"><span>Impressions</span><strong>{variant.impressions.toLocaleString()}</strong></div>
        <div className="variant-stat"><span>Clicks</span><strong>{variant.clicks.toLocaleString()}</strong></div>
        <div className="variant-stat"><span>Click-through rate</span><strong>{variant.impressions ? (variant.clicks / variant.impressions * 100).toFixed(2) : "0.00"}%</strong></div>
        <div className="variant-stat"><span>Conversions</span><strong>{variant.conversions}</strong></div>
      </div>)}</div>
    </section>)}
  </>;
}

function MetricForm({ campaignId, experimentId, label, action, busy }: { campaignId: string; experimentId: string; label: string; action: Action; busy: boolean }) {
  return <details><summary>Import cumulative results</summary><form onSubmit={(event) => {
    event.preventDefault(); const values = new FormData(event.currentTarget);
    action(`/campaigns/${campaignId}/experiments/${experimentId}/metrics`, { label, impressions: Number(values.get("impressions")), clicks: Number(values.get("clicks")), conversions: Number(values.get("conversions")), source: values.get("source") });
  }}><fieldset disabled={busy}>{["impressions", "clicks", "conversions"].map((key) => <label key={key}>{title(key)}<input name={key} type="number" min={0} max={1000000000} required /></label>)}<label>Evidence source<input name="source" required maxLength={1000} placeholder="Platform export, date range or report reference" /></label><button className="button secondary">Save results</button></fieldset></form></details>;
}
