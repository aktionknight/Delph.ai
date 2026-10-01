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

export function MemoryPanel({ campaign, action, busy }: { campaign: Campaign; action: Action; busy: boolean }) {
  return <><div className="section-heading"><div><h2>Make the next launch a little smarter.</h2><p className="muted">Keep useful hypotheses with the campaign, or save them to your brand.</p></div><button className="button primary" disabled={busy || !campaign.experiments.length} onClick={() => action(`/campaigns/${campaign.id}/learnings`)}><Sparkles size={16} /> Generate learnings</button></div><div className="notice">Learnings reflect recorded evidence. Demo experiments remain simulated; imported results require validation. Saving is always your choice.</div>{!campaign.learnings.length ? <div className="panel"><Empty title="A place for the lessons worth keeping.">Create an experiment first, then generate evidence-linked hypotheses from its recorded results.</Empty></div> : <div className="learning-grid">{campaign.learnings.map((learning) => <section className="panel learning-card" key={learning.id}><div className="row"><BookOpen size={21} /><Badge tone="amber">Evidence-linked hypothesis</Badge></div><h3>{learning.statement}</h3><p>{typeof learning.evidence === "string" ? learning.evidence : JSON.stringify(learning.evidence)}</p><p className="small muted">Heuristic confidence: {Math.round(learning.confidence * 100)}% · not statistical certainty</p><button className="button secondary" disabled={busy || learning.saved_to_brand} onClick={() => action(`/campaigns/${campaign.id}/learnings/${learning.id}/save`)}>{learning.saved_to_brand ? <><Check size={16} /> Saved to Brand Brain</> : <><PlusIcon /> Save to Brand Brain</>}</button></section>)}</div>}</>;
}
function PlusIcon() { return <span aria-hidden="true">+</span>; }

