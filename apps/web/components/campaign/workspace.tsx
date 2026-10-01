"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BarChart3, BookOpen, CalendarDays, Check, Download, FlaskConical, Layers, ListChecks, RefreshCw, Route, ShieldCheck, Sparkles } from "lucide-react";
import { api, title, type Asset, type Brand, type Campaign } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { DeliverablesPanel } from "@/components/deliverables/panel";
import { Badge, ErrorNotice, Loading, PageHeading, Status } from "@/components/ui";

import { StrategyPanel } from "@/components/strategist/panel";

import { TimelinePanel } from "@/components/timeline/panel";

import { ContentPanel } from "@/components/canvas/panel";

import { ExperimentsPanel } from "@/components/experiments/panel";

import { AnalyticsPanel } from "@/components/analytics/panel";

import { TracePanel } from "@/components/trace/panel";

import { MemoryPanel } from "@/components/context/panel";

import { ApprovalPanel } from "@/components/approval/panel";

import { DeleteControl } from "@/components/delete-control";
import { useAgentJob } from "@/hooks/use-agent-job";
import { SectionPrompt, SectionReview, savedPrompt } from "./section-controls";

type Tab = "strategy" | "timeline" | "content" | "approvals" | "experiments" | "analytics" | "trace" | "memory" | "deliverables";
const tabs: { id: Tab; name: string; icon: typeof Sparkles }[] = [{ id: "strategy", name: "Strategy", icon: Route }, { id: "timeline", name: "Timeline", icon: CalendarDays }, { id: "content", name: "Content canvas", icon: Layers }, { id: "approvals", name: "Approvals", icon: ShieldCheck }, { id: "experiments", name: "Experiments", icon: FlaskConical }, { id: "analytics", name: "Analytics", icon: BarChart3 }, { id: "trace", name: "Activity trace", icon: ListChecks }, { id: "memory", name: "Memory", icon: BookOpen }, { id: "deliverables", name: "Deliverables", icon: Download }];
export type Action = (path: string, body?: unknown, method?: string) => void;

export function Workspace({ id, brands }: { id: string; brands: Brand[] }) {
  const [tab, setTab] = useState<Tab>("strategy");
  const [progress, setProgress] = useState("");
  const waitForJob = useAgentJob(setProgress);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["campaign", id], queryFn: () => api<Campaign>(`/campaigns/${id}`), refetchInterval: (q) => q.state.data?.assets.some((a) => ["scheduled", "publishing"].includes(a.status)) ? 5000 : false });
  const mutation = useMutation({ mutationFn: async ({ path, body, method }: { path: string; body?: unknown; method: string }) => {
    const operation = path.match(/^\/campaigns\/[^/]+\/(strategy|directions|timeline|assets|insights|learnings)$/)?.[1];
    if (operation && method === "POST" && query.data?.generation_mode === "gemini") {
      setProgress("Queuing AI agents…");
      const instructions = body && typeof body === "object" && "prompt" in body ? body.prompt : undefined;
      const job = await api<{ id: string }>(`/campaigns/${id}/jobs`, "POST", {
        operation, ...(operation === "assets" ? { asset: body } : { prompt: instructions })
      });
      await waitForJob(job.id);
      setProgress("");
      return api<Campaign>(`/campaigns/${id}`);
    }
    return api<Campaign | Asset>(path, method, body);
  }, onSuccess: (result) => {
    if ("brand_id" in result) client.setQueryData(["campaign", id], result);
    else void client.invalidateQueries({ queryKey: ["campaign", id] });
    void client.invalidateQueries({ queryKey: ["campaigns"] });
    void client.invalidateQueries({ queryKey: ["brands"] });
    void client.invalidateQueries({ queryKey: ["analytics", id] });
  } });
  const action: Action = (path, body, method = "POST") => mutation.mutate({ path, body, method });
  const campaign = query.data;
  const [exportError, setExportError] = useState<unknown>(null);
  const [exporting, setExporting] = useState(false);
  async function exportCampaign() {
    setExportError(null); setExporting(true);
    try {
      await downloadFile(`/api/campaigns/${encodeURIComponent(id)}/export`, `campaign-${id}.pdf`, "application/pdf");
    } catch (error) { setExportError(error); } finally { setExporting(false); }
  }
  if (query.isPending) return <Loading />;
  if (!campaign) return <><ErrorNotice error={query.error} /><button className="button secondary" onClick={() => void query.refetch()}>Retry campaign</button></>;
  const brand = brands.find((item) => item.id === campaign.brand_id);
  const pending = campaign.assets.filter((asset) => asset.status === "needs_review").length;
  return <><DeleteControl kind="campaign" id={id} disabled={mutation.isPending || campaign.assets.some((a) => ["publishing", "publish_unknown"].includes(a.status))} /><Link className="back-link" href="/"><ArrowLeft size={15} /> All campaigns</Link><PageHeading eyebrow={`${brand?.name || "CAMPAIGN"} / ${campaign.duration_days}-DAY LAUNCH`} title={campaign.name} description={campaign.goal} action={<button className="button secondary" disabled={exporting} onClick={() => void exportCampaign()}><Download size={16} />{exporting ? "Exporting…" : "Export campaign"}</button>} /><div className="campaign-meta"><Status value={campaign.status} /><span>{campaign.platforms.map(title).join(" + ")}</span><span>{campaign.assets.length} content assets</span><Badge>{campaign.generation_mode === "gemini" ? "Gemini AI generation" : "Deterministic demo"}</Badge></div><div className="workflow-track" aria-label="Campaign progress">{[{ label: "Brief", done: true }, { label: "Strategy", done: !!campaign.strategy }, { label: "Direction", done: !!campaign.selected_direction }, { label: "Timeline", done: !!campaign.timeline.length }, { label: "Content", done: !!campaign.assets.length }, { label: "Approval", done: campaign.assets.some((asset) => ["approved", "published"].includes(asset.status)) }, { label: "Learning", done: !!campaign.learnings.length }].map((step, index) => <div className={step.done ? "workflow-step done" : "workflow-step"} key={step.label}><span>{step.done ? <Check size={13} /> : index + 1}</span>{step.label}</div>)}</div><nav className="campaign-tabs" aria-label="Campaign sections">{tabs.map(({ id: tabId, name, icon: Icon }) => <button key={tabId} aria-current={tab === tabId ? "page" : undefined} className={tab === tabId ? "selected" : ""} onClick={() => { setTab(tabId); mutation.reset(); }}><Icon size={16} />{name}{tabId === "approvals" && pending > 0 && <span className="tab-count">{pending}</span>}</button>)}</nav><ErrorNotice error={query.error || mutation.error || exportError} />{mutation.isPending && <div className="action-progress" role="status"><RefreshCw size={14} className="spin" /> {progress || "Saving campaign state…"}</div>}
      {tab === "strategy" && <StrategyPanel key={campaign.id} campaign={campaign} brand={brand} action={action} busy={mutation.isPending} onNext={() => setTab("timeline")} />}
      {tab === "timeline" && <TimelinePanel key={campaign.id} campaign={campaign} action={action} busy={mutation.isPending} onNext={() => setTab("content")} />}
      {tab === "content" && <ContentPanel key={campaign.id} campaign={campaign} brand={brand} action={action} busy={mutation.isPending} approvalsOnly={false} />}
      {tab === "approvals" && <ApprovalPanel key={campaign.id} campaign={campaign} brand={brand} action={action} busy={mutation.isPending} />}
      {tab === "experiments" && <ExperimentsPanel key={campaign.id} campaign={campaign} action={action} busy={mutation.isPending} />}
      {tab === "analytics" && <AnalyticsPanel key={campaign.id} id={id} campaign={campaign} action={action} busy={mutation.isPending} />}
      {tab === "trace" && <TracePanel campaign={campaign} refresh={() => void query.refetch()} />}
      {tab === "memory" && <MemorySection key={campaign.id} campaign={campaign} action={action} busy={mutation.isPending} />}
      {tab === "deliverables" && <DeliverablesPanel key={campaign.id} campaign={campaign} />}
  </>;
}

function MemorySection({ campaign, action, busy }: { campaign: Campaign; action: Action; busy: boolean }) {
  const [prompt, setPrompt] = useState(savedPrompt(campaign, "learnings"));
  const promptedAction: Action = (path, body, method) => action(path,
    path === `/campaigns/${campaign.id}/learnings` ? { prompt } : body, method);
  return <><div className="panel"><SectionPrompt section="learnings" value={prompt} onChange={setPrompt} busy={busy} /></div>
    <MemoryPanel campaign={campaign} action={promptedAction} busy={busy} />
    <div className="panel"><SectionReview campaign={campaign} section="learnings" action={action} busy={busy} /></div></>;
}

