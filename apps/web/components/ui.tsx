"use client";
import { AlertCircle, LoaderCircle, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { title, type Brand } from "@/lib/api";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "green" | "amber" | "red" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Status({ value }: { value: string }) {
  return <Badge tone={/approved|published|passed|completed/.test(value) ? "green" : /fail|reject/.test(value) ? "red" : /review|change/.test(value) ? "amber" : "neutral"}>{title(value)}</Badge>;
}
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="notice error" role="alert"><AlertCircle size={18} /><span>{error instanceof Error ? error.message : String(error)}</span></div>;
}
export function Loading() { return <div className="loading" role="status"><LoaderCircle className="spin" size={22} /> Loading your workspace…</div>; }
export function Empty({ title: heading, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><Sparkles size={25} /></div><h3>{heading}</h3><p>{children}</p>{action}</div>;
}
export function PageHeading({ eyebrow, title: heading, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{heading}</h1><p className="muted">{description}</p></div>{action}</div>;
}
export function Sources({ refs, brand }: { refs: string[]; brand?: Brand }) {
  if (!refs.length) return <p className="muted small">No source citations attached.</p>;
  return <div className="sources"><p className="label">Grounded in {refs.length} source{refs.length === 1 ? "" : "s"}</p>{refs.map((ref) => {
    const source = brand?.sources.find((item) => item.id === ref);
    return <details key={ref}><summary>{source?.name || ref}</summary><p className="source-text">{source?.text || "This reference is no longer available in the current brand context."}</p></details>;
  })}</div>;
}
