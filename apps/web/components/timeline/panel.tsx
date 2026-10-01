"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { title, type Campaign } from "@/lib/api";
import { Badge, Empty } from "@/components/ui";
import { TimelineEditor } from "@/components/strategist/planning-editor";
import { SectionPrompt, SectionReview, savedPrompt } from "@/components/campaign/section-controls";
import type { Action } from "@/components/campaign/workspace";

export function TimelinePanel({ campaign, action, busy, onNext }: {
  campaign: Campaign; action: Action; busy: boolean; onNext: () => void;
}) {
  const [prompt, setPrompt] = useState(savedPrompt(campaign, "timeline"));
  return <><div className="section-heading"><div><h2>A rhythm for your launch</h2><p className="muted">A {campaign.duration_days}-day plan, grounded in your selected direction.</p></div></div>
    <div className="panel"><SectionPrompt section="timeline" value={prompt} onChange={setPrompt} busy={busy} disabled={!campaign.selected_direction}
      generateLabel={campaign.timeline.length ? "Rebalance timeline" : "Generate timeline"} onGenerate={() => action(`/campaigns/${campaign.id}/timeline`, { prompt })} />
      {campaign.timeline.length > 0 && <p className="small muted">Regenerating replaces the schedule. Existing assets keep their original timeline reference; remap them in the canvas before publication.</p>}
    </div>
    {!campaign.selected_direction ? <Empty title="Choose a creative direction first">Your timeline needs a strategy and selected direction. Head to the Strategy tab to set them.</Empty> : !campaign.timeline.length ? <div className="panel"><Empty title="Make every stage of the launch count.">Generate a sequence that brings your audience from awareness to action.</Empty></div> : <>
      <div className="timeline">{campaign.timeline.map((item) => {
        const linked = campaign.assets.filter((asset) => asset.timeline_item_id === item.id);
        return <div className="timeline-item" key={item.id}><div className="timeline-day"><span>DAY</span><strong>{String(item.day).padStart(2, "0")}</strong></div>
          <div className="timeline-content"><div className="row"><Badge tone="green">{title(item.stage)}</Badge><span className="small muted">{title(item.platform)} · {title(item.asset_type)}</span></div>
            <h3>{item.objective}</h3><p className="small muted">{linked.length} mapped deliverable{linked.length === 1 ? "" : "s"}{linked.length > 0 ? ` · ${linked.map((asset) => title(asset.status)).join(", ")}` : " · create one in the content canvas"}</p>
            <TimelineEditor key={JSON.stringify(item)} campaign={campaign} item={item} action={action} busy={busy} />
          </div></div>;
      })}</div>
      <div className="panel"><SectionReview campaign={campaign} section="timeline" action={action} busy={busy} /></div>
      <div className="next-step"><span>Your plan is ready. Bring the first asset to life.</span><button className="button primary" onClick={onNext}>Open content canvas <ArrowRight size={16} /></button></div>
    </>}
  </>;
}
