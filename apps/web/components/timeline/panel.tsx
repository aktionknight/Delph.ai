"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BarChart3, BookOpen, CalendarDays, Check, CheckCircle2, Download, FlaskConical, Layers, ListChecks, RefreshCw, Route, ShieldCheck, Sparkles } from "lucide-react";
import { api, currentVersion, platforms, title, type Analytics, type Asset, type Brand, type Campaign } from "@/lib/api";
import { Badge, Empty, ErrorNotice, Loading, PageHeading, Sources, Status } from "@/components/ui";
import { AssetEditor } from "@/components/canvas/asset-editor";
import { StrategyEditor, TimelineEditor } from "@/components/strategist/planning-editor";

import type { Action } from "@/components/campaign/workspace";

export function TimelinePanel({ campaign, action, busy, onNext }: { campaign: Campaign; action: Action; busy: boolean; onNext: () => void }) {
  return <><div className="section-heading"><div><h2>A rhythm for your launch</h2><p className="muted">A {campaign.duration_days}-day plan, grounded in your selected direction.</p></div>{campaign.selected_direction && <button className="button primary" disabled={busy || !campaign.selected_direction} onClick={() => action(`/campaigns/${campaign.id}/timeline`)}><CalendarDays size={16} /> {campaign.timeline.length ? "Rebalance with AI" : "Generate timeline"}</button>}</div>{!campaign.selected_direction ? <Empty title="Choose a creative direction first">Your timeline needs a strategy and selected direction. Head to the Strategy tab to set them.</Empty> : !campaign.timeline.length ? <div className="panel"><Empty title="Make every stage of the launch count.">Generate a sequence that brings your audience from awareness to action.</Empty></div> : <><div className="timeline">{campaign.timeline.map((item) => <div className="timeline-item" key={item.id}><div className="timeline-day"><span>DAY</span><strong>{String(item.day).padStart(2, "0")}</strong></div><div className="timeline-content"><div className="row"><Badge tone="green">{title(item.stage)}</Badge><span className="small muted">{title(item.platform)} · {title(item.asset_type)}</span></div><h3>{item.objective}</h3><TimelineEditor key={JSON.stringify(item)} campaign={campaign} item={item} action={action} busy={busy} /></div></div>)}</div><div className="next-step"><span>Your plan is ready. Bring the first asset to life.</span><button className="button primary" onClick={onNext}>Open content canvas <ArrowRight size={16} /></button></div></>}</>;
}

