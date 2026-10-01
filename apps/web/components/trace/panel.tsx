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

export function TracePanel({ campaign, refresh }: { campaign: Campaign; refresh: () => void }) {
  return <><div className="section-heading"><div><h2>Every decision leaves a trace.</h2><p className="muted">Persisted campaign activity, from context retrieval to human review.</p></div><button className="button secondary" onClick={refresh}><RefreshCw size={15} /> Refresh activity</button></div><p className="small muted">This is a saved event history. Background job streaming is not enabled in this demo.</p><div className="panel trace-panel">{campaign.trace.length ? [...campaign.trace].reverse().map((event) => <div className="trace-event" key={event.id}><span className={/fail|error/.test(event.status) ? "trace-dot failure" : "trace-dot"} /><div><div className="row"><h3>{title(event.event_type)}</h3><time>{new Date(event.timestamp).toLocaleString()}</time></div><p>{event.message}</p><Status value={event.status} /></div></div>) : <Empty title="Your story starts here.">Campaign actions will add persisted events to this history.</Empty>}</div></>;
}

