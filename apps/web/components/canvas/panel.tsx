"use client";

import { useState } from "react";
import { CalendarDays, Sparkles } from "lucide-react";
import { currentVersion, platforms, title, type Brand, type Campaign } from "@/lib/api";
import { Badge, Empty, Status } from "@/components/ui";
import { AssetEditor } from "@/components/canvas/asset-editor";
import type { Action } from "@/components/campaign/workspace";

export function ContentPanel({ campaign, brand, action, busy, approvalsOnly }: { campaign: Campaign; brand?: Brand; action: Action; busy: boolean; approvalsOnly: boolean }) {
  const [selectedId, setSelectedId] = useState("");
  const [platform, setPlatform] = useState(campaign.platforms[0] || "");
  const [timelineId, setTimelineId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [demonstrateFailure, setDemonstrateFailure] = useState(false);
  const selectedPlatform = campaign.platforms.includes(platform) ? platform : campaign.platforms[0];
  const scheduledItems = campaign.timeline.filter((item) => item.platform === selectedPlatform);
  const scheduled = scheduledItems.find((item) => item.id === timelineId) || scheduledItems[0];
  const assets = approvalsOnly ? campaign.assets.filter((asset) => !["published", "rejected"].includes(asset.status)) : campaign.assets;
  const selected = assets.find((asset) => asset.id === selectedId) || assets[0];

  function generate() {
    if (!scheduled) return;
    action(`/campaigns/${campaign.id}/assets`, {
      platform: scheduled.platform,
      asset_type: scheduled.asset_type,
      timeline_item_id: scheduled.id,
      prompt: prompt.trim() || undefined,
      demonstrate_failure: demonstrateFailure,
    });
  }

  return <>
    <div className="section-heading">
      <div><h2>{approvalsOnly ? "Your judgment is the final step." : "One strategy. Every channel."}</h2><p className="muted">{approvalsOnly ? "Fine tune the current version, inspect its evidence, and explicitly approve." : "Create platform copy, campaign statics, and Instagram narration for your timeline."}</p></div>
      <Badge>{campaign.generation_mode === "gemini" ? "AI writer + evaluator" : "Template-based demo"}</Badge>
    </div>
    {!approvalsOnly && <section className="panel canvas-generator" aria-label="Create a timeline deliverable">
      <div className="generation-bar">
        <label>Social platform<select value={selectedPlatform || ""} disabled={busy} onChange={(event) => { setPlatform(event.target.value); setTimelineId(""); setPrompt(""); }}>
          {campaign.platforms.map((item) => <option key={item} value={item}>{platforms.find((entry) => entry.id === item)?.name || title(item)}</option>)}
        </select></label>
        <label>Timeline deliverable<select value={scheduled?.id || ""} disabled={busy || !scheduledItems.length} onChange={(event) => { setTimelineId(event.target.value); setPrompt(""); }}>
          {!scheduledItems.length && <option value="">No scheduled deliverables</option>}
          {scheduledItems.map((item) => <option key={item.id} value={item.id}>Day {item.day} · {title(item.asset_type)} · {item.objective}</option>)}
        </select></label>
        <button className="button primary" disabled={busy || !scheduled} onClick={generate}><Sparkles size={16} /> Generate text / caption</button>
      </div>
      {scheduled && <div className="canvas-schedule"><CalendarDays size={16} /><div><strong>Day {scheduled.day} · {title(scheduled.stage)} · {title(scheduled.asset_type)}</strong><p className="small muted">{scheduled.objective}</p></div></div>}
      <label>Custom content instructions<textarea rows={3} maxLength={4000} value={prompt} disabled={busy} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the angle, tone, audience, or caption you want for this deliverable." /></label>
      <p className="small muted">The draft uses your brief, Brand Brain, selected direction, and scheduled objective. Add an image or Instagram narration after the text passes evaluation.</p>
      <details><summary className="small muted">Evaluation demo</summary><label className="inline-check"><input type="checkbox" checked={demonstrateFailure} disabled={busy} onChange={(event) => setDemonstrateFailure(event.target.checked)} /> Demonstrate an unsupported-claim failure</label></details>
    </section>}
    {!campaign.timeline.length && <div className="notice">Generate your campaign timeline before creating content.</div>}
    {!approvalsOnly && campaign.timeline.length > 0 && !scheduled && <div className="notice">This platform has no timeline items. Add a deliverable in the timeline or choose another platform.</div>}
    {!assets.length ? <div className="panel"><Empty title={approvalsOnly ? "No assets ready for review" : "Your canvas is ready for the first draft."}>{approvalsOnly ? "Create an asset in the content canvas. Its evaluation and approval history will appear here." : "Choose a timeline deliverable to create its text. Images and narration stay attached to the same deliverable and version history."}</Empty></div> : <div className="content-layout">
      <div className="asset-list">{assets.map((asset) => {
        const scheduledContext = asset.timeline_snapshot || campaign.timeline.find((item) => item.id === asset.timeline_item_id);
        return <button className={selected?.id === asset.id ? "asset-list-item selected" : "asset-list-item"} key={asset.id} onClick={() => setSelectedId(asset.id)}>
          <div className="row"><span className="label">{platforms.find((item) => item.id === asset.platform)?.name || title(asset.platform)}</span><span className="small muted">v{asset.current_version}</span></div>
          <h3>{currentVersion(asset)?.hook || title(asset.asset_type)}</h3>
          <p className="small muted">{scheduledContext ? `Day ${scheduledContext.day} · ${title(asset.asset_type)}` : "Legacy asset · no timeline mapping"}</p>
          <Status value={asset.status} />
        </button>;
      })}</div>
      {selected && <AssetEditor key={`${selected.id}-${selected.current_version}`} asset={selected} campaign={campaign} brand={brand} action={action} busy={busy} />}
    </div>}
  </>;
}
