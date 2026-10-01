"use client";

import { useState } from "react";
import { CheckCircle2, MessageSquare, Sparkles } from "lucide-react";
import type { Campaign } from "@/lib/api";
import { Badge } from "@/components/ui";
import type { Action } from "./workspace";

export type CampaignSection = "brief" | "strategy" | "direction" | "timeline" | "insights" | "learnings";
export const sectionNames: Record<CampaignSection, string> = {
  brief: "Campaign brief", strategy: "Strategy", direction: "Creative direction",
  timeline: "Campaign timeline", insights: "Analytics insights", learnings: "Campaign learnings"
};
type SectionReviewRecord = {
  section: CampaignSection; revision: number; decision: "approved" | "changes_requested";
  feedback: string; created_at: string; user_id: string;
};
type ReviewableCampaign = Campaign & {
  generation_prompts?: Record<string, string>;
  section_revisions?: Record<string, number>;
  reviews?: SectionReviewRecord[];
};

export function savedPrompt(campaign: Campaign, section: CampaignSection) {
  return (campaign as ReviewableCampaign).generation_prompts?.[section] || "";
}

export function SectionPrompt({ section, value, onChange, busy, onGenerate, generateLabel, disabled = false }: {
  section: CampaignSection; value: string; onChange: (value: string) => void; busy: boolean;
  onGenerate?: () => void; generateLabel?: string; disabled?: boolean;
}) {
  return <div className="section-controls">
    <label>Custom instructions for {sectionNames[section].toLowerCase()}
      <textarea value={value} onChange={(event) => onChange(event.target.value)} disabled={busy}
        maxLength={2000} rows={3} placeholder="Add audience details, tone, constraints, or changes you want the agent to make." />
    </label>
    <p className="small muted">Your instructions accompany the campaign and brand context. Generating a revision requires a new review.</p>
    {onGenerate && <button className="button primary" disabled={busy || disabled} onClick={onGenerate}>
      <Sparkles size={16} />{generateLabel || "Generate with instructions"}
    </button>}
  </div>;
}

export function sectionAvailable(campaign: Campaign, section: CampaignSection) {
  switch (section) {
    case "brief": return !!campaign.brief;
    case "strategy": return !!campaign.strategy;
    case "direction": return !!campaign.selected_direction;
    case "timeline": return campaign.timeline.length > 0;
    case "insights": return (campaign.insights?.length || 0) > 0;
    case "learnings": return campaign.learnings.length > 0;
  }
}

export function SectionReview({ campaign, section, action, busy }: {
  campaign: Campaign; section: CampaignSection; action: Action; busy: boolean;
}) {
  const [feedback, setFeedback] = useState("");
  const data = campaign as ReviewableCampaign;
  const revision = data.section_revisions?.[section] || 0;
  const history = (data.reviews || []).filter((review) => review.section === section);
  const current = history.filter((review) => review.revision === revision).at(-1);
  const available = sectionAvailable(campaign, section);
  const submit = (decision: "approved" | "changes_requested") => action(`/campaigns/${campaign.id}/reviews`, {
    section, revision, decision, feedback: feedback.trim()
  });
  return <section className="section-review">
    <div className="row"><h3><MessageSquare size={16} /> Review {sectionNames[section].toLowerCase()}</h3>
      <Badge tone={current?.decision === "approved" ? "green" : "amber"}>
        {current?.decision === "approved" ? "Approved" : current?.decision === "changes_requested" ? "Changes requested" : "Awaiting review"} · revision {revision}
      </Badge>
    </div>
    {!available && <p className="small muted">Complete this section before recording its review.</p>}
    <label>Human feedback<textarea value={feedback} onChange={(event) => setFeedback(event.target.value)}
      disabled={busy || !available} rows={2} maxLength={2000} placeholder="Record approval notes or the specific changes needed." /></label>
    <div className="row"><button className="button secondary" disabled={busy || !available || !feedback.trim()} onClick={() => submit("changes_requested")}>Request changes</button>
      <button className="button primary" disabled={busy || !available} onClick={() => submit("approved")}><CheckCircle2 size={15} />Approve current revision</button></div>
    <p className="small muted">Reviews are saved to campaign history. Section approval does not approve content assets for publication.</p>
    {history.length > 0 && <details className="review-history"><summary>Review history ({history.length})</summary>
      {history.slice().reverse().map((review, index) => <div key={`${review.created_at}-${review.revision}-${index}`}>
        <p><strong>{review.decision === "approved" ? "Approved" : "Changes requested"}</strong> · revision {review.revision}{review.revision !== revision ? " · previous revision" : ""}</p>
        {review.feedback && <p>{review.feedback}</p>}<time className="small muted">{new Date(review.created_at).toLocaleString()}</time>
      </div>)}
    </details>}
  </section>;
}
