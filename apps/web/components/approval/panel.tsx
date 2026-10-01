"use client";

import { useState } from "react";
import { ContentPanel } from "@/components/canvas/panel";
import { BriefEditor, StrategyEditor, TimelineEditor } from "@/components/strategist/planning-editor";
import { SectionPrompt, SectionReview, sectionNames, savedPrompt, type CampaignSection } from "@/components/campaign/section-controls";
import type { Brand, Campaign } from "@/lib/api";
import type { Action } from "@/components/campaign/workspace";

const sections: CampaignSection[] = ["brief", "strategy", "direction", "timeline", "insights", "learnings"];

export function ApprovalPanel(props: { campaign: Campaign; brand?: Brand; action: Action; busy: boolean }) {
  return <><section className="panel"><h2>Campaign review and fine tuning</h2>
    <p className="muted">Review each planning section, request changes, or generate a revision with your instructions. Every saved revision needs its own review.</p>
    {sections.map((section) => <PlanningReview key={section} {...props} section={section} />)}
  </section><ContentPanel {...props} approvalsOnly /></>;
}

function PlanningReview({ campaign, section, action, busy }: {
  campaign: Campaign; section: CampaignSection; action: Action; busy: boolean;
}) {
  const [prompt, setPrompt] = useState(savedPrompt(campaign, section));
  const operation = section === "direction" ? "directions" : section;
  const disabled = section === "direction" ? !campaign.strategy : section === "timeline" ? !campaign.selected_direction : section === "learnings" ? !campaign.experiments.length : false;
  const selectedDirection = campaign.strategy?.creative_directions.find((direction) => direction.id === campaign.selected_direction);
  return <details className="planning-review"><summary>{sectionNames[section]}</summary>
    {section === "brief" && <><p>{campaign.brief}</p><BriefEditor key={`${campaign.name}-${campaign.brief}-${campaign.goal}-${campaign.audience}`} campaign={campaign} action={action} busy={busy} /></>}
    {section === "strategy" && campaign.strategy && <><p>{campaign.strategy.positioning}</p><p>{campaign.strategy.core_message}</p><StrategyEditor key={JSON.stringify(campaign.strategy)} campaign={campaign} action={action} busy={busy} /></>}
    {section === "direction" && <>{selectedDirection ? <><h3>{selectedDirection.name}</h3><p>{selectedDirection.description}</p><p className="muted">{selectedDirection.rationale}</p></> : <p className="muted">Select a creative direction in Strategy before approving it.</p>}
      {campaign.strategy && <label>Creative direction<select disabled={busy} value={campaign.selected_direction || ""} onChange={(event) => { if (event.target.value) action(`/campaigns/${campaign.id}/direction`, { direction_id: event.target.value }); }}><option value="">Select a direction</option>{campaign.strategy.creative_directions.map((direction) => <option key={direction.id} value={direction.id}>{direction.name}</option>)}</select></label>}
    </>}
    {section === "timeline" && campaign.timeline.map((item) => <div key={item.id}><p>Day {item.day}: {item.objective}</p><TimelineEditor key={JSON.stringify(item)} campaign={campaign} item={item} action={action} busy={busy} /></div>)}
    {section === "insights" && campaign.insights?.map((insight, index) => <p key={index}>{insight}</p>)}
    {section === "learnings" && campaign.learnings.map((learning) => <p key={learning.id}>{learning.statement}</p>)}
    {section !== "brief" && <SectionPrompt section={section} value={prompt} onChange={setPrompt} busy={busy} disabled={disabled}
      generateLabel={`Revise ${sectionNames[section].toLowerCase()}`} onGenerate={() => action(`/campaigns/${campaign.id}/${operation}`, { prompt })} />}
    <SectionReview campaign={campaign} section={section} action={action} busy={busy} />
  </details>;
}
