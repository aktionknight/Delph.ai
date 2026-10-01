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

export function AnalyticsPanel({ id, campaign, action, busy }: { id: string; campaign: Campaign; action: Action; busy: boolean }) {
  const query = useQuery({ queryKey: ["analytics", id], queryFn: () => api<Analytics>(`/campaigns/${id}/analytics`) });
  if (query.isPending) return <Loading />;
  if (!query.data) return <><ErrorNotice error={query.error} /><button className="button secondary" onClick={() => void query.refetch()}>Retry analytics</button></>;
  const analytics = query.data;
  const max = Math.max(1, ...analytics.platforms.map((item) => item.impressions));
  return <><div className="section-heading"><div><h2>Make room for what you learn.</h2><p className="muted">Explore recorded campaign performance.</p></div><Badge tone="amber">{analytics.is_demo ? "Simulated metrics · not real performance" : "Manually imported metrics"}</Badge></div><div className="metric-grid">{[{ label: "Impressions", value: analytics.impressions.toLocaleString() }, { label: "Clicks", value: analytics.clicks.toLocaleString() }, { label: "Conversions", value: analytics.conversions.toLocaleString() }, { label: "Click-through rate", value: `${(Number(analytics.ctr) * 100).toFixed(2)}%` }].map((metric) => <div className="metric-card" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><p>{analytics.is_demo ? "Simulated campaign data" : "User supplied campaign data"}</p></div>)}</div><div className="analytics-layout"><section className="panel"><h3>Impressions by platform</h3><p className="small muted">{analytics.is_demo ? "Deterministic simulation" : "Recorded metrics"}</p><div className="bar-chart">{analytics.platforms.map((platform) => <div key={platform.platform}><div className="row"><span>{title(platform.platform)}</span><strong>{platform.impressions.toLocaleString()}</strong></div><div className="bar-track"><span style={{ width: `${platform.impressions / max * 100}%` }} /></div><p className="small muted">{platform.clicks} clicks · {platform.conversions} conversions</p></div>)}</div></section><section className="panel observations"><Sparkles size={22} /><h3>What the numbers suggest</h3>{campaign.generation_mode === "gemini" && <button className="button secondary" disabled={busy} onClick={() => action(`/campaigns/${id}/insights`)}>Analyze with AI</button>}{campaign.insights?.map((insight, index) => <p key={`ai-${index}`}>{insight}</p>)}{analytics.observations.map((observation, index) => <p key={index}>{observation}</p>)}<span className="small muted">Observations are hypotheses; imported numbers are not independently verified.</span></section></div></>;
}

