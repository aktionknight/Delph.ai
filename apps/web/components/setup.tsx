"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, FileText, Plus, ShieldCheck, Upload } from "lucide-react";
import { api, platforms, type Brand, type Campaign } from "@/lib/api";
import { SourceActions } from "./source-actions";
import { RemoveBrand } from "./context/remove-brand";
import { Badge, Empty, ErrorNotice, Loading, PageHeading } from "./ui";

export function NewCampaign({ brands, loading, error }: { brands: Brand[]; loading: boolean; error: unknown }) {
  const router = useRouter();
  const client = useQueryClient();
  const [channels, setChannels] = useState(["linkedin", "instagram", "x"]);
  const mutation = useMutation({ mutationFn: (body: unknown) => api<Campaign>("/campaigns", "POST", body), onSuccess: (campaign) => {
    void client.invalidateQueries({ queryKey: ["campaigns"] });
    client.setQueryData(["campaign", campaign.id], campaign);
    router.push(`/campaigns/${campaign.id}`);
  } });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    mutation.mutate({ brand_id: form.get("brand_id"), name: form.get("name"), brief: form.get("brief"), goal: form.get("goal"), audience: form.get("audience"), platforms: channels, duration_days: Number(form.get("duration_days")) });
  }
  return <><Link className="back-link" href="/"><ArrowLeft size={15} /> Back to overview</Link><PageHeading eyebrow="GIVE YOUR IDEA A DIRECTION" title="What are we launching?" description="A useful brief is the starting point. Your campaign grows from here." /><ErrorNotice error={error} />{loading ? <Loading /> : !brands.length ? <Empty title="Create a brand first" action={<Link href="/brands" className="button primary">Set up Brand Brain</Link>}>Campaigns need a brand to keep their context connected.</Empty> : <div className="form-layout"><form className="panel form-panel" onSubmit={submit}><div className="panel-heading"><span className="step-circle">01</span><div><h2>The campaign brief</h2><p className="muted">Make it specific. You can build the strategy next.</p></div></div><fieldset disabled={mutation.isPending}><label>Campaign name<input name="name" required maxLength={160} placeholder="e.g. The next chapter of your product" /></label><label>What are you launching?<textarea name="brief" required minLength={10} maxLength={10000} rows={5} placeholder="Tell us about your product, the problem it solves, and what makes this launch matter." /></label><div className="form-grid"><label>Campaign goal<input name="goal" required maxLength={200} placeholder="Build awareness and early signups" /></label><label>Campaign duration<select name="duration_days" defaultValue="14"><option value="7">7 days · a focused sprint</option><option value="14">14 days · a considered launch</option><option value="30">30 days · build momentum</option></select></label></div><label>Who is this for?<input name="audience" required maxLength={200} placeholder="e.g. Small marketing teams building their next big launch" /></label><label>Brand context<select name="brand_id" required>{brands.map((brand) => <option key={brand.id} value={brand.id}>{brand.name} · {brand.sources.length} sources</option>)}</select></label><div><span className="label">Where will your campaign live?</span><div className="channel-options">{platforms.map((platform) => <label className={channels.includes(platform.id) ? "channel-option selected" : "channel-option"} key={platform.id}><input type="checkbox" checked={channels.includes(platform.id)} onChange={(event) => setChannels(event.target.checked ? [...channels, platform.id] : channels.filter((item) => item !== platform.id))} />{platform.name}</label>)}</div></div><ErrorNotice error={mutation.error} /><div className="form-footer"><span className="small muted">Your campaign will be saved to your workspace.</span><button className="button primary" disabled={!channels.length} type="submit">{mutation.isPending ? "Creating…" : "Create campaign"}<ArrowRight size={16} /></button></div></fieldset></form><aside className="form-aside"><div className="context-note"><SparkleDecoration /><h3>A brief becomes<br />a connected plan.</h3><p>Everything you create builds on the same campaign state.</p><ol><li><strong>Ground it</strong><span>Add the facts behind your brand.</span></li><li><strong>Shape it</strong><span>Choose a strategy and creative direction.</span></li><li><strong>Make it yours</strong><span>Review content before it moves forward.</span></li><li><strong>Keep learning</strong><span>Compare variants and save evidence-linked insights.</span></li></ol></div><div className="notice"><ShieldCheck size={20} /><p>You stay in control. Passing evaluation never substitutes for your approval.</p></div></aside></div>}</>;
}

function SparkleDecoration() { return <span className="big-sparkle" aria-hidden="true">✦</span>; }

export function BrandBrain({ brands, loading, error }: { brands: Brand[]; loading: boolean; error: unknown }) {
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const brand = brands.find((item) => item.id === selected) || brands[0];
  return <><PageHeading eyebrow="THE CONTEXT BEHIND EVERY CAMPAIGN" title="Your Brand Brain." description="The facts, voice, and guardrails that keep your campaigns grounded." action={<button className="button primary" onClick={() => setCreating(true)}><Plus size={16} /> Add brand</button>} /><ErrorNotice error={error} />{loading ? <Loading /> : <><div className="brand-tabs">{brands.map((item) => <button key={item.id} className={brand?.id === item.id && !creating ? "brand-tab active" : "brand-tab"} onClick={() => { setSelected(item.id); setCreating(false); }}>{item.name}<Badge>{item.sources.length} sources</Badge></button>)}</div>{creating || !brand ? <BrandForm key="new" onSaved={(saved) => { setSelected(saved.id); setCreating(false); }} /> : <div className="brand-layout"><div className="brand-col"><BrandForm key={`brand-form-${brand.id}`} brand={brand} onSaved={() => {}} /><RemoveBrand key={brand.id} brand={brand} onRemoved={() => setSelected("")} /></div><div className="brand-col"><SourceForm key={`source-form-${brand.id}`} brand={brand} /><div className="panel"><div className="panel-heading"><FileText size={20} /><div><h2>Source library</h2><p className="muted">Source text is visible wherever it is cited.</p></div></div>{brand.sources.length ? <div className="source-library">{brand.sources.map((source) => <details key={source.id}><summary><span><FileText size={17} /> {source.name}</span><Badge>{source.source_type.replaceAll("_", " ")}</Badge></summary><p className="source-text">{source.text}</p><SourceActions brandId={brand.id} source={source} /></details>)}</div> : <Empty title="Add your first source">Upload a document or paste a note to ground campaign generation in your own context.</Empty>}<p className="small muted">AI mode retrieves embedded source chunks. Demo mode uses keyword matching.</p></div></div></div>}</>}</>;
}

function BrandForm({ brand, onSaved }: { brand?: Brand; onSaved: (brand: Brand) => void }) {
  const client = useQueryClient();
  const mutation = useMutation({ mutationFn: (body: unknown) => api<Brand>(brand ? `/brands/${brand.id}` : "/brands", brand ? "PATCH" : "POST", body), onSuccess: (saved) => { void client.invalidateQueries({ queryKey: ["brands"] }); onSaved(saved); } });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const lines = (name: string) => String(form.get(name)).split("\n").map((line) => line.trim()).filter(Boolean);
    mutation.mutate({ name: form.get("name"), description: form.get("description"), voice: form.get("voice"), approved_claims: lines("approved_claims"), forbidden_phrases: lines("forbidden_phrases") });
  }
  return <form className="panel form-panel" onSubmit={submit}><h2>{brand ? "Brand identity & guardrails" : "Create a brand"}</h2><p className="muted">Be precise about what your content can say.</p><fieldset disabled={mutation.isPending}><label>Brand name<input name="name" required maxLength={120} defaultValue={brand?.name || ""} /></label><label>What does your brand do?<textarea name="description" required maxLength={10000} rows={3} defaultValue={brand?.description || ""} /></label><label>Voice & tone<input name="voice" required maxLength={200} defaultValue={brand?.voice || ""} placeholder="Clear, human, confident" /></label><label>Approved claims<span className="field-hint">One evidenced claim per line.</span><textarea name="approved_claims" maxLength={20000} rows={3} defaultValue={brand?.approved_claims.join("\n") || ""} /></label><label>Forbidden phrases<span className="field-hint">One phrase per line.</span><textarea name="forbidden_phrases" maxLength={10000} rows={2} defaultValue={brand?.forbidden_phrases.join("\n") || ""} /></label><ErrorNotice error={mutation.error} /><div className="form-footer">{mutation.isSuccess && <span className="success-text" role="status">Brand context saved.</span>}<button className="button primary" type="submit">{mutation.isPending ? "Saving…" : brand ? "Save brand context" : "Create brand"}</button></div></fieldset></form>;
}

function SourceForm({ brand }: { brand: Brand }) {
  const client = useQueryClient();
  const [mode, setMode] = useState<"text" | "upload">("text");
  const [validation, setValidation] = useState("");
  const mutation = useMutation({ mutationFn: ({ body, upload }: { body: unknown; upload: boolean }) => api<Brand>(`/brands/${brand.id}/sources${upload ? "/upload" : ""}`, "POST", body), onSuccess: () => { void client.invalidateQueries({ queryKey: ["brands"] }); } });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidation("");
    const form = event.currentTarget;
    const data = new FormData(form);
    if (mode === "upload") {
      const file = data.get("file") as File;
      if (!file || !/\.(pdf|txt|md)$/i.test(file.name)) { setValidation("Choose a PDF, TXT, or Markdown document."); return; }
      if (file.size > 5 * 1024 * 1024) { setValidation("This document exceeds the 5 MB upload limit."); return; }
      mutation.mutate({ body: data, upload: true }, { onSuccess: () => form.reset() });
    } else {
      mutation.mutate({ body: { name: data.get("name"), text: data.get("text"), source_type: "manual_note" }, upload: false }, { onSuccess: () => form.reset() });
    }
  }
  return <form className="panel form-panel" onSubmit={submit}><h2>Add knowledge</h2><p className="muted">Product facts, audience research, or brand guidelines.</p><div className="segmented"><button type="button" className={mode === "text" ? "selected" : ""} onClick={() => { setMode("text"); mutation.reset(); }}>Paste a note</button><button type="button" className={mode === "upload" ? "selected" : ""} onClick={() => { setMode("upload"); mutation.reset(); }}>Upload a document</button></div><fieldset disabled={mutation.isPending}>{mode === "text" ? <><label>Source name<input name="name" required maxLength={200} placeholder="Product facts · September" /></label><label>Source text<textarea name="text" required minLength={10} maxLength={100000} rows={5} placeholder="Paste the information the campaign should use…" /></label></> : <label className="upload-zone"><Upload size={25} /><strong>Add a source document</strong><span>PDF, TXT, or Markdown · up to 5 MB</span><input name="file" type="file" accept=".pdf,.txt,.md" required /></label>}<ErrorNotice error={validation || mutation.error} /><div className="form-footer">{mutation.isSuccess && <span className="success-text" role="status">Source added to Brand Brain.</span>}<button className="button primary" type="submit">{mutation.isPending ? "Adding source…" : "Add source"}<Plus size={16} /></button></div></fieldset></form>;
}
