"use client";
import { type FormEvent } from "react";
import { type Campaign, platforms } from "@/lib/api";
import { type Action } from "@/components/campaign/workspace";

export function BriefEditor({ campaign, action, busy }: { campaign: Campaign; action: Action; busy: boolean }) {
  return <details><summary>Fine-tune campaign brief</summary>
    <p className="small muted">Saving a brief revision clears strategy, selected direction, and timeline so they can be rebuilt. Existing assets and review history are retained.</p>
    <form onSubmit={(event) => {
      event.preventDefault(); const data = new FormData(event.currentTarget);
      action(`/campaigns/${campaign.id}`, { name: data.get("name"), brief: data.get("brief"), goal: data.get("goal"), audience: data.get("audience") }, "PATCH");
    }}><fieldset disabled={busy}>
      <label>Campaign name<input name="name" required maxLength={200} defaultValue={campaign.name} /></label>
      <label>Brief<textarea name="brief" required maxLength={10000} defaultValue={campaign.brief} /></label>
      <label>Goal<textarea name="goal" required maxLength={2000} defaultValue={campaign.goal} /></label>
      <label>Audience<textarea name="audience" required maxLength={2000} defaultValue={campaign.audience} /></label>
      <button className="button secondary">Save brief revision</button>
    </fieldset></form>
  </details>;
}

export function StrategyEditor({ campaign, action, busy }: { campaign: Campaign; action: Action; busy: boolean }) {
  if (!campaign.strategy) return null;
  const strategy = campaign.strategy;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    action(`/campaigns/${campaign.id}/strategy`, { positioning: data.get("positioning"), core_message: data.get("core_message"), audience_summary: data.get("audience_summary"), content_pillars: String(data.get("content_pillars")).split("\n").map((v) => v.trim()).filter(Boolean) }, "PATCH");
  }
  return <details><summary>Edit strategy</summary><p className="small muted">Saving records the previous strategy and clears the timeline so you can rebuild it.</p><form onSubmit={submit}><fieldset disabled={busy}><label>Positioning<textarea name="positioning" required maxLength={10000} defaultValue={strategy.positioning} /></label><label>Core message<textarea name="core_message" required maxLength={10000} defaultValue={strategy.core_message} /></label><label>Audience<textarea name="audience_summary" required maxLength={10000} defaultValue={strategy.audience_summary} /></label><label>Content pillars, one per line<textarea name="content_pillars" required defaultValue={strategy.content_pillars.join("\n")} /></label><button className="button secondary">Save strategy revision</button></fieldset></form></details>;
}

export function TimelineEditor({ campaign, item, action, busy }: { campaign: Campaign; item: Campaign["timeline"][number]; action: Action; busy: boolean }) {
  return <details><summary>Edit schedule item</summary><form onSubmit={(event) => {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    action(`/campaigns/${campaign.id}/timeline/${item.id}`, { day: Number(data.get("day")), stage: data.get("stage"), platform: data.get("platform"), asset_type: data.get("asset_type"), objective: data.get("objective") }, "PATCH");
  }}><fieldset disabled={busy}><label>Day<input name="day" type="number" min={1} max={campaign.duration_days} required defaultValue={item.day} /></label><label>Stage<input name="stage" required maxLength={200} defaultValue={item.stage} /></label><label>Platform<select name="platform" defaultValue={item.platform}>{platforms.filter((p) => campaign.platforms.includes(p.id)).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Asset type<select name="asset_type" defaultValue={item.asset_type}>{["post", "reel", "thread", "carousel", "story"].map((type) => <option key={type}>{type}</option>)}</select></label><label>Objective<textarea name="objective" required maxLength={10000} defaultValue={item.objective} /></label><button className="button secondary">Save schedule item</button></fieldset></form></details>;
}
