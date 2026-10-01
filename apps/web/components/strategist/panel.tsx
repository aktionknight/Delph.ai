"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Check, CheckCircle2, ShieldCheck } from "lucide-react";
import type { Brand, Campaign } from "@/lib/api";
import { Badge, Empty, Sources } from "@/components/ui";
import { StrategyEditor, BriefEditor } from "./planning-editor";
import { SectionPrompt, SectionReview, savedPrompt } from "@/components/campaign/section-controls";
import type { Action } from "@/components/campaign/workspace";

export function StrategyPanel({ campaign, brand, action, busy, onNext }: {
  campaign: Campaign; brand?: Brand; action: Action; busy: boolean; onNext: () => void;
}) {
  const strategy = campaign.strategy;
  const [strategyPrompt, setStrategyPrompt] = useState(savedPrompt(campaign, "strategy"));
  const [directionPrompt, setDirectionPrompt] = useState(savedPrompt(campaign, "direction"));
  return <div className="strategy-layout"><div>
    <div className="panel"><SectionPrompt section="strategy" value={strategyPrompt} onChange={setStrategyPrompt} busy={busy}
      generateLabel={strategy ? "Regenerate strategy" : "Generate strategy"}
      onGenerate={() => action(`/campaigns/${campaign.id}/strategy`, { prompt: strategyPrompt })} /></div>
    {!strategy ? <div className="panel"><Empty title="Give your launch a point of view.">
      Build positioning, content pillars, and creative directions from your brief and brand sources. The active generation mode is shown above.
    </Empty></div> : <>
      <div className="panel strategy-summary"><div className="row"><h2>A strategy with a clear center.</h2><Badge tone="green"><CheckCircle2 size={12} /> Generated</Badge></div>
        <div className="strategy-statement"><span className="label">POSITIONING</span><h3>{strategy.positioning}</h3></div>
        <div className="strategy-fields"><div><span className="label">CORE MESSAGE</span><p>{strategy.core_message}</p></div><div><span className="label">AUDIENCE</span><p>{strategy.audience_summary}</p></div></div>
        <span className="label">CONTENT PILLARS</span><div className="pillar-list">{strategy.content_pillars.map((pillar, index) => <div key={`${index}-${pillar}`}><span>0{index + 1}</span>{pillar}</div>)}</div>
        <Sources refs={strategy.source_refs} brand={brand} />
        <StrategyEditor key={JSON.stringify(strategy)} campaign={campaign} action={action} busy={busy} />
        <SectionReview campaign={campaign} section="strategy" action={action} busy={busy} />
      </div>
      <div className="section-heading"><div><h2>Choose your creative direction</h2><p className="muted">This choice shapes your timeline and every content asset.</p></div></div>
      <div className="panel"><SectionPrompt section="direction" value={directionPrompt} onChange={setDirectionPrompt} busy={busy}
        generateLabel="Generate new creative directions" onGenerate={() => action(`/campaigns/${campaign.id}/directions`, { prompt: directionPrompt })} />
        <p className="small muted">New directions clear the selected direction and timeline. Existing asset versions remain in their history.</p>
      </div>
      <div className="direction-grid">{strategy.creative_directions.map((direction, index) => <div key={direction.id} className={campaign.selected_direction === direction.id ? "direction-card selected" : "direction-card"}>
        <div className="row"><span className="direction-number">0{index + 1}</span>{campaign.selected_direction === direction.id && <Badge tone="green"><Check size={12} /> Selected</Badge>}</div>
        <h3>{direction.name}</h3><p>{direction.description}</p><div className="direction-rationale"><span className="label">WHY THIS WORKS</span><p>{direction.rationale}</p></div>
        <button className={campaign.selected_direction === direction.id ? "button secondary full" : "button primary full"} disabled={busy || campaign.selected_direction === direction.id}
          onClick={() => action(`/campaigns/${campaign.id}/direction`, { direction_id: direction.id })}>{campaign.selected_direction === direction.id ? "Current direction" : "Choose direction"}</button>
      </div>)}</div>
      <div className="panel"><SectionReview campaign={campaign} section="direction" action={action} busy={busy} /></div>
      {campaign.selected_direction && <div className="next-step"><span>Direction set. Give your campaign a rhythm.</span><button className="button primary" onClick={onNext}>Build the timeline <ArrowRight size={16} /></button></div>}
    </>}
  </div><aside><div className="panel brief-card"><h3>The original brief</h3><p>{campaign.brief}</p>
    <div className="brief-detail"><span className="label">AUDIENCE</span><p>{campaign.audience}</p></div>
    <div className="brief-detail"><span className="label">BRAND VOICE</span><p>{brand?.voice || "Loading brand context…"}</p></div>
    <BriefEditor key={`${campaign.name}-${campaign.brief}-${campaign.goal}-${campaign.audience}`} campaign={campaign} action={action} busy={busy} />
    <SectionReview campaign={campaign} section="brief" action={action} busy={busy} />
    <Link href="/brands" className="text-link">Open Brand Brain <ArrowRight size={14} /></Link></div>
    {strategy && <div className="panel assumptions"><h3>Assumptions to review</h3><p className="small muted">These are working assumptions, not established facts.</p><ul>{strategy.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul></div>}
    <div className="notice"><ShieldCheck size={20} /><p>Review the strategy against your actual goals and evidence.</p></div>
  </aside></div>;
}
