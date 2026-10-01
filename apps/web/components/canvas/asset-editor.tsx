"use client";

import { useState, type FormEvent } from "react";
import { CalendarDays, Check, CheckCircle2, Copy, FileClock, FileText, ImagePlus, Mic, RefreshCw, Save, ShieldCheck, XCircle } from "lucide-react";
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
  const [activeTab, setActiveTab] = useState<"text" | "image" | "voice" | "history">("text");
  const [hook, setHook] = useState(version.hook);
  const [body, setBody] = useState(version.body);
  const [caption, setCaption] = useState(version.caption || "");
  const [cta, setCta] = useState(version.cta);
  const [revisionPrompt, setRevisionPrompt] = useState("");
  const [imagePrompt, setImagePrompt] = useState("");
  const [voicePrompt, setVoicePrompt] = useState("");
  const [voice, setVoice] = useState(() => {
    const priorVoice = version.media_items?.find((media) => media.kind === "voiceover")?.voice || (version.media?.kind === "voiceover" ? version.media.voice : undefined);
    return voices.some((item) => item.id === priorVoice) ? priorVoice! : "";
  });
  const [mediaReviewed, setMediaReviewed] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<unknown>(null);
  const dirty = hook !== version.hook || body !== version.body || cta !== version.cta || caption !== (version.caption || "");
  const isPublished = asset.status === "published";
  const isInstagram = asset.platform === "instagram";
  const currentTimelineItem = campaign?.timeline.find((item) => item.id === asset.timeline_item_id);
  const scheduled = asset.timeline_snapshot || currentTimelineItem;
  const scheduleChanged = !!asset.timeline_snapshot && !!campaign && (!currentTimelineItem || (["day", "stage", "platform", "asset_type", "objective"] as const).some((field) => asset.timeline_snapshot![field] !== currentTimelineItem[field]));
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
      ...(kind === "voiceover" && voice ? { voice } : {}),
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
      {scheduled ? (
        <div className="deliverable-bar">
          <CalendarDays size={16} />
          <span><strong>Day {scheduled.day}</strong> · {title(scheduled.stage)} · {title(asset.platform)} {title(asset.asset_type)}</span>
          <span className="muted" style={{ marginLeft: 'auto', fontSize: '0.8rem' }}>{scheduled.objective}</span>
          {scheduleChanged && <div className="notice" style={{ width: '100%', margin: '0.5rem 0 0' }}>Schedule updated. Consider creating a replacement from the revised timeline.</div>}
        </div>
      ) : (
        <div className="notice" style={{ margin: 0 }}>This legacy asset has no timeline mapping.</div>
      )}

      <div className="sub-tabs">
        <button type="button" className={activeTab === "text" ? "sub-tab active" : "sub-tab"} onClick={() => setActiveTab("text")}>
          <FileText size={15} /> Text & Caption
        </button>
        <button type="button" className={activeTab === "image" ? "sub-tab active" : "sub-tab"} onClick={() => setActiveTab("image")}>
          <ImagePlus size={15} /> Static Image {images.length > 0 && <span className="tab-pill">{images.length}</span>}
        </button>
        {isInstagram && (
          <button type="button" className={activeTab === "voice" ? "sub-tab active" : "sub-tab"} onClick={() => setActiveTab("voice")}>
            <Mic size={15} /> Voice Narration {narration.length > 0 && <span className="tab-pill">{narration.length}</span>}
          </button>
        )}
        <button type="button" className={activeTab === "history" ? "sub-tab active" : "sub-tab"} onClick={() => setActiveTab("history")}>
          <FileClock size={15} /> Versions & Sources <span className="tab-pill">v{version.version}</span>
        </button>
      </div>

      {activeTab === "text" && (
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
      )}

      {activeTab === "image" && (
        <section className="panel media-section" aria-label="Static image generation">
          <div className="panel-heading"><ImagePlus size={18} /><h3>Campaign static / image</h3><Badge>{title(asset.platform)}</Badge></div>
          <p className="small muted">Generate a static from the Brand Brain, selected direction, timeline objective, and evaluated copy.</p>
          {(dirty || !version.evaluation.passed) && <div className="notice">Save your edits and pass text evaluation before generating images.</div>}
          {images.map((media) => <figure className="media-preview" key={media.id}><img src={`/api/assets/${asset.id}/media/${media.id}`} alt={media.alt_text || "Campaign static"} /><figcaption className="small muted">{media.alt_text}</figcaption></figure>)}
          <label>Custom image instructions<textarea rows={3} maxLength={2000} value={imagePrompt} disabled={busy} onChange={(event) => setImagePrompt(event.target.value)} placeholder="Describe composition, visual mood, and any layout preferences." /></label>
          <button className="button secondary" disabled={mediaDisabled} onClick={() => generateMedia("image")}><ImagePlus size={16} />{images.length ? "Generate a new static" : "Generate static image"}</button>
          <p className="small muted">Images use the server-configured Gemini image model and the existing Gemini key. Google requires paid-tier image access; generated statics still need your review.</p>
        </section>
      )}

      {activeTab === "voice" && isInstagram && (
        <section className="panel media-section" aria-label="Instagram voice generation">
          <div className="panel-heading"><Mic size={18} /><h3>Instagram narration</h3><Badge>Natural TTS</Badge></div>
          <p className="small muted">The creative agent prepares spoken narration from this timeline item and current copy, then a neural TTS voice reads it.</p>
          {(dirty || !version.evaluation.passed) && <div className="notice">Save your edits and pass text evaluation before generating narration.</div>}
          {narration.map((media) => <div className="media-preview" key={media.id}><audio controls preload="metadata" src={`/api/assets/${asset.id}/media/${media.id}`} /><p className="small muted">{media.voice || "Generated narration"}</p>{media.script && <details><summary>Review spoken script</summary><p className="pre-wrap">{media.script}</p></details>}</div>)}
          <label>Narration voice<select value={voice} disabled={busy} onChange={(event) => setVoice(event.target.value)}><option value="">Server default voice</option>{voices.map((item) => <option key={item.id} value={item.id}>{item.name} · Edge TTS</option>)}</select></label>
          <label>Custom narration instructions<textarea rows={3} maxLength={2000} value={voicePrompt} disabled={busy} onChange={(event) => setVoicePrompt(event.target.value)} placeholder="Ask for a warm spoken intro, a shorter reel script, or a more conversational delivery." /></label>
          <button className="button secondary" disabled={mediaDisabled} onClick={() => generateMedia("voiceover")}><Mic size={16} />{narration.length ? "Generate new narration" : "Generate natural voice"}</button>
          <p className="small muted">Listen to the audio and verify pronunciation and claims before approving. Image and audio remain attached to this deliverable together.</p>
        </section>
      )}

      {activeTab === "history" && (
        <>
          <div className="panel"><Sources refs={version.source_refs} brand={brand} /></div>
          <details className="panel history-panel" open><summary><FileClock size={16} /> Version history <Badge>{asset.versions.length} versions</Badge></summary><div className="history-list">{[...asset.versions].reverse().map((old) => <details key={old.version}><summary><strong>Version {old.version}</strong><span>{new Date(old.created_at).toLocaleString()}</span><Badge tone={old.evaluation.passed ? "green" : "red"}>{old.evaluation.passed ? "Passed" : "Failed"}</Badge></summary><h4>{old.hook}</h4><p className="pre-wrap">{old.body}</p>{old.caption && <><strong>Caption</strong><p className="pre-wrap">{old.caption}</p></>}<p>{old.cta}</p><p className="small muted">{(old.media_items?.length || (old.media ? 1 : 0))} media items</p>{old.evaluation.issues.map((issue, index) => <p className="failure-text" key={index}>{issue}</p>)}</details>)}</div></details>
        </>
      )}
    </div>
    <aside className="asset-inspector">
      <section className="panel quality-panel">
        <div className="panel-heading"><ShieldCheck size={17} /><h3>Copy evaluation</h3><Badge tone={version.evaluation.passed ? "green" : "red"}>{version.evaluation.passed ? "ALL PASS" : "REVIEW"}</Badge></div>
        <p className="small muted">{version.evaluation.model ? "AI evaluator + safety checks" : "Demo rule checks"} · version {version.version}</p>
        <div className="quality-checks">{Object.entries(version.evaluation.checks).map(([name, passed]) => <div key={name}>{passed ? <CheckCircle2 size={14} /> : <XCircle size={14} className="failure-text" />}<span>{title(name)}</span><strong className={passed ? "" : "failure-text"}>{passed ? "Pass" : "Failed"}</strong></div>)}</div>
        {version.evaluation.issues.length > 0 && <div className="evaluation-issues">{version.evaluation.issues.map((issue, index) => <p key={index}>{issue}</p>)}</div>}
        <p className="small muted">AI and rule checks can miss errors. Verify claims, brand fit, captions, and generated media before approval.</p>
      </section>
      <section className="panel approval-panel">
        <div className="row"><span className="eyebrow">HUMAN REVIEW</span><span className="small muted">STAGE 05</span></div>
        <h3>{isPublished ? "Publication recorded" : asset.status === "approved" ? "Current version approved" : "Your sign-off is required"}</h3>
        <p>Publication requires a passing evaluation and your explicit approval of this exact version.</p>
        {dirty && <div className="notice">Save and evaluate your edits before reviewing.</div>}
        {mediaItems.length > 0 && <label className="inline-check"><input type="checkbox" checked={mediaReviewed} disabled={busy || isPublished} onChange={(event) => setMediaReviewed(event.target.checked)} /> I reviewed all {mediaItems.length} generated media {mediaItems.length === 1 ? "item" : "items"} in version {version.version}, including images and audio.</label>}
        <label>Review feedback<textarea rows={3} maxLength={2000} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="Note what to improve or why this version is ready." disabled={busy || isPublished} /></label>
        <button className="button secondary full" disabled={busy || dirty || !feedback.trim() || isPublished} onClick={() => revise("all", feedback)}><RefreshCw size={14} /> Revise with review feedback</button>
        <button className="button primary full" disabled={busy || dirty || !version.evaluation.passed || (mediaItems.length > 0 && !mediaReviewed) || asset.status === "approved" || isPublished} onClick={() => decision("approve")}><ShieldCheck size={15} /> Approve version {version.version}</button>
        <div className="review-secondary"><button disabled={busy || dirty || isPublished} onClick={() => decision("request-changes")}>Request changes</button><button disabled={busy || dirty || isPublished} onClick={() => decision("reject")}>Reject version</button></div>
        {asset.status === "approved" && <button className="button secondary full" disabled={busy || dirty} onClick={() => action(`/assets/${asset.id}/publish`, { version: asset.current_version })}><Check size={14} /> Record publication</button>}
        {isPublished && <Badge tone="green">Publication recorded</Badge>}
        <p className="small muted">Publication records a workflow status. It does not post to any social platform.</p>
      </section>
      <section className="panel approval-history"><h3>Review history</h3>{asset.approvals.length ? [...asset.approvals].reverse().map((approval, index) => <div key={index}><div className="row"><Status value={approval.decision} /><span className="small muted">v{approval.version}</span></div><p>{approval.feedback || "No review note added."}</p><time>{new Date(approval.created_at).toLocaleString()}</time></div>) : <p className="small muted">No human decisions recorded yet.</p>}</section>
    </aside>
  </>;
}
