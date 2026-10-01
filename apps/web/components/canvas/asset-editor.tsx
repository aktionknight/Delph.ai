"use client";

import { useState, type FormEvent } from "react";
import { CalendarDays, Check, CheckCircle2, Copy, FileClock, ImagePlus, Mic, RefreshCw, Save, ShieldCheck, XCircle } from "lucide-react";
import { currentVersion, title, type Asset, type Brand, type Campaign } from "@/lib/api";
import { Badge, ErrorNotice, Sources, Status } from "@/components/ui";
import type { Action } from "@/components/campaign/workspace";

const voices = [
  { id: "en-US-AriaNeural", name: "Aria · English (US)" },
  { id: "en-US-GuyNeural", name: "Guy · English (US)" },
  { id: "en-GB-SoniaNeural", name: "Sonia · English (UK)" },
  { id: "en-IN-NeerjaNeural", name: "Neerja · English (India)" },
];

export function AssetEditor({ asset, brand, campaign, action, busy }: { asset: Asset; brand?: Brand; campaign?: Campaign; action: Action; busy: boolean }) {
  const version = currentVersion(asset);
  const [hook, setHook] = useState(version.hook);
  const [body, setBody] = useState(version.body);
  const [caption, setCaption] = useState(version.caption || "");
  const [cta, setCta] = useState(version.cta);
  const [revisionPrompt, setRevisionPrompt] = useState("");
  const [imagePrompt, setImagePrompt] = useState("");
  const [voicePrompt, setVoicePrompt] = useState("");
  const [voice, setVoice] = useState(voices[0].id);
  const [mediaReviewed, setMediaReviewed] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<unknown>(null);
  const dirty = hook !== version.hook || body !== version.body || cta !== version.cta || caption !== (version.caption || "");
  const isPublished = asset.status === "published";
  const isInstagram = asset.platform === "instagram";
  const currentTimelineItem = campaign?.timeline.find((item) => item.id === asset.timeline_item_id);
  const scheduled = asset.timeline_snapshot || currentTimelineItem;
  const mediaItems = version.media_items?.length ? version.media_items : version.media ? [version.media] : [];
  const images = mediaItems.filter((media) => media.kind === "image");
  const narration = mediaItems.filter((media) => media.kind === "voiceover");
  const mediaDisabled = busy || dirty || !version.evaluation.passed || !scheduled;

  function save(event: FormEvent) {
    event.preventDefault();
    action(`/assets/${asset.id}`, { hook, body, caption, cta }, "PATCH");
  }
  function decision(kind: string) {
    action(`/assets/${asset.id}/${kind}`, { version: asset.current_version, feedback, media_reviewed: mediaReviewed });
  }
  function revise(section: string, prompt = revisionPrompt) {
    action(`/assets/${asset.id}/regenerate`, { section, prompt: prompt.trim() || undefined });
  }
  function generateMedia(kind: "image" | "voiceover") {
    action(`/assets/${asset.id}/media`, {
      version: asset.current_version,
      kind,
      prompt: (kind === "image" ? imagePrompt : voicePrompt).trim() || undefined,
      ...(kind === "voiceover" ? { voice } : {}),
    });
  }
  async function copy() {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText([hook, isInstagram && caption ? caption : body, cta].join("\n\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch { setCopyError(new Error("Clipboard access was denied. Select the content and copy it manually.")); }
  }

  return <>
    <div className="asset-main">
      <section className="panel deliverable-context" aria-label="Deliverable timeline mapping">
        <div className="panel-heading"><CalendarDays size={18} /><h3>Timeline deliverable</h3></div>
        {scheduled ? <><strong>Day {scheduled.day} · {title(scheduled.stage)} · {title(asset.platform)} {title(asset.asset_type)}</strong><p>{scheduled.objective}</p><p className="small muted">Text, statics, and narration share this scheduled objective.</p>{asset.timeline_snapshot && !currentTimelineItem && campaign && <div className="notice">This asset retains its original schedule after a timeline revision. Review its placement before publication.</div>}</> : <div className="notice">This legacy asset has no timeline mapping. Create its replacement from a timeline deliverable before generating media.</div>}
      </section>
      <form className="panel editor-panel" onSubmit={save}>
        <div className="panel-heading"><h2>Platform text and caption</h2><Badge>{title(asset.platform)}</Badge><span className="small muted">v{version.version}</span></div>
        <div className="editor-meta"><span className="brand-round">{brand?.name.charAt(0) || "D"}</span><div><strong>{brand?.name || "Brand content"}</strong><span>{title(asset.asset_type)} · versioned content</span></div><Status value={asset.status} /></div>
        <fieldset disabled={busy}>
          <label>Opening hook<textarea className="hook-editor" required maxLength={10000} rows={3} value={hook} onChange={(event) => setHook(event.target.value)} /></label>
          <label>{isInstagram && asset.asset_type === "reel" ? "Reel narration / scene script" : asset.platform === "x" && asset.asset_type === "thread" ? "Thread text" : "Post text"}<textarea className="body-editor" required maxLength={10000} rows={10} value={body} onChange={(event) => setBody(event.target.value)} /></label>
          {(isInstagram || !!version.caption) && <label>{isInstagram ? "Instagram caption" : "Platform caption"}<textarea rows={5} maxLength={10000} value={caption} onChange={(event) => setCaption(event.target.value)} placeholder="Fine tune the caption that accompanies this deliverable." /></label>}
          <label>Call to action<textarea required maxLength={10000} rows={2} value={cta} onChange={(event) => setCta(event.target.value)} /></label>
          <div className="editor-count">{[hook, body, caption, cta].filter(Boolean).join("\n\n").length} characters · {dirty ? "Unsaved changes" : "Version saved"}</div>
          <ErrorNotice error={copyError} />
          <div className="editor-actions"><button className="button primary" type="submit" disabled={!dirty}><Save size={14} /> Save and evaluate new version</button><button className="button secondary" type="button" onClick={() => void copy()}><Copy size={14} />{copied ? "Copied" : isInstagram ? "Copy caption" : "Copy text"}</button></div>
        </fieldset>
        <label>Custom AI revision prompt<textarea rows={3} maxLength={2000} value={revisionPrompt} disabled={busy} onChange={(event) => setRevisionPrompt(event.target.value)} placeholder="Make the hook more conversational, shorten the caption, or adjust the tone for this platform." /></label>
        <div className="quick-refine"><span>REFINE THIS VERSION</span><button className="button compact" type="button" disabled={busy || dirty} onClick={() => revise("hook")}>New hook</button><button className="button compact" type="button" disabled={busy || dirty} onClick={() => revise("cta")}>New CTA</button><button className="button compact" type="button" disabled={busy || dirty} onClick={() => revise("all")}><RefreshCw size={12} />{version.evaluation.passed ? "Revise draft" : "Repair asset"}</button></div>
        <p className="small muted">Each edit or generation creates a new version and clears approval. Review the resulting text and every retained media item before sign-off.</p>
        {version.generation_prompt && <details><summary>Instructions used for this version</summary><p className="pre-wrap small">{version.generation_prompt}</p></details>}
      </form>
      <section className="panel media-section" aria-label="Static image generation">
        <div className="panel-heading"><ImagePlus size={18} /><h3>Campaign static / image</h3><Badge>{title(asset.platform)}</Badge></div>
        <p className="small muted">Generate a static from the Brand Brain, selected direction, timeline objective, and evaluated copy.</p>
        {images.map((media) => <figure className="media-preview" key={media.id}><img src={`/api/assets/${asset.id}/media/${media.id}`} alt={media.alt_text || "Campaign static"} /><figcaption className="small muted">{media.alt_text}</figcaption></figure>)}
        <label>Custom image instructions<textarea rows={3} maxLength={2000} value={imagePrompt} disabled={busy} onChange={(event) => setImagePrompt(event.target.value)} placeholder="Describe composition, visual mood, and any layout preferences." /></label>
        <button className="button secondary" disabled={mediaDisabled} onClick={() => generateMedia("image")}><ImagePlus size={16} />{images.length ? "Generate a new static" : "Generate static image"}</button>
        <p className="small muted">Gemini image generation requires image model access. Its API has no free image tier; the server blocks image requests unless paid image access is explicitly enabled.</p>
      </section>
      {isInstagram && <section className="panel media-section" aria-label="Instagram voice generation">
        <div className="panel-heading"><Mic size={18} /><h3>Instagram narration</h3><Badge>Natural TTS</Badge></div>
     