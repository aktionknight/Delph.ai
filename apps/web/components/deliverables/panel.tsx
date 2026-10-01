"use client";

import { useState } from "react";
import { Archive, CalendarDays, Download, FileText, Image as ImageIcon, Mic } from "lucide-react";
import { title, type Asset, type Campaign, type Media, type TimelineItem } from "@/lib/api";
import { downloadFile, saveText } from "@/lib/download";
import { Badge, Empty, ErrorNotice, Status } from "@/components/ui";

type Group = { key: string; item?: TimelineItem; assets: Asset[]; historical?: boolean };
type DownloadAction = (path: string, filename: string, type?: string) => Promise<void>;

export function DeliverablesPanel({ campaign }: { campaign: Campaign }) {
  const [error, setError] = useState<unknown>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const activeIds = new Set(campaign.timeline.map((item) => item.id));
  const groups: Group[] = [...campaign.timeline].sort((a, b) => a.day - b.day).map((item) => ({
    key: item.id, item, assets: campaign.assets.filter((asset) => asset.timeline_item_id === item.id)
  }));
  const historical = new Map<string, Group>();
  const unmapped: Asset[] = [];
  for (const asset of campaign.assets) {
    if (asset.timeline_item_id && activeIds.has(asset.timeline_item_id)) continue;
    if (asset.timeline_item_id || asset.timeline_snapshot) {
      const key = asset.timeline_item_id || asset.timeline_snapshot!.id;
      const group = historical.get(key) || { key: `historical-${key}`, item: asset.timeline_snapshot, assets: [], historical: true };
      group.assets.push(asset);
      historical.set(key, group);
    } else unmapped.push(asset);
  }
  const download: DownloadAction = async (path, filename, type) => {
    setError(null); setNotice(""); setDownloading(path);
    try {
      await downloadFile(path, filename, type);
      setNotice("Download started. Check your browser downloads.");
    } catch (problem) { setError(problem); } finally { setDownloading(null); }
  };
  const campaignZip = `/api/campaigns/${encodeURIComponent(campaign.id)}/deliverables/download`;
  return <section className="deliverables-panel" aria-label="Campaign deliverables">
    <div className="section-heading"><div><h2>Your campaign deliverables</h2><p className="muted">Current copy, scripts, images and voiceovers, organized by timeline item.</p></div>
      <button className="button primary" disabled={!!downloading || !campaign.assets.length} onClick={() => void download(campaignZip, `campaign-${campaign.id}-deliverables.zip`, "application/zip")}><Archive size={16} />{downloading === campaignZip ? "Preparing ZIP…" : "Download all assets"}</button>
    </div>
    <div className="deliverables-summary"><Badge>{campaign.assets.length} assets</Badge><Badge>{campaign.timeline.length} timeline items</Badge><p className="small muted">Downloads include current versions, including drafts. Review each asset’s status before use. Export campaign above downloads the full campaign as a PDF.</p></div>
    <ErrorNotice error={error} />
    {notice && <p className="small muted" role="status">{notice}</p>}
    {!groups.length && !campaign.assets.length && <div className="panel"><Empty title="Your deliverables will appear here">Build a timeline and create assets in the content canvas to collect your campaign files.</Empty></div>}
    {groups.map((group) => <DeliverableGroup key={group.key} group={group} download={download} downloading={downloading} />)}
    {historical.size > 0 && <div className="deliverables-history"><h3>Previous timeline items</h3><p className="small muted">These assets retain their original schedule after the timeline was replaced.</p>
      {[...historical.values()].sort((a, b) => (a.item?.day ?? Infinity) - (b.item?.day ?? Infinity)).map((group) => <DeliverableGroup key={group.key} group={group} download={download} downloading={downloading} />)}
    </div>}
    {unmapped.length > 0 && <DeliverableGroup group={{ key: "unmapped", assets: unmapped }} download={download} downloading={downloading} />}
  </section>;
}

function DeliverableGroup({ group, download, downloading }: { group: Group; download: DownloadAction; downloading: string | null }) {
  const item = group.item;
  return <section className="deliverables-group panel" aria-label={item ? `Day ${item.day}: ${item.objective}` : group.historical ? "Previous timeline item" : "Unmapped assets"}>
    <header className="deliverables-group-heading"><CalendarDays size={20} /><div>
      <div className="row">{item && <Badge>Day {String(item.day).padStart(2, "0")}</Badge>}{item && <span className="small muted">{title(item.platform)} · {title(item.asset_type)} · {title(item.stage)}</span>}{group.historical && <Badge tone="amber">Previous schedule</Badge>}</div>
      <h3>{item?.objective || (group.historical ? "Original schedule unavailable" : "Unmapped assets")}</h3>
      {!item && <p className="small muted">{group.historical ? "The timeline link is retained, but its original details are unavailable." : "These legacy assets have no saved timeline link."}</p>}
    </div><span className="small muted">{group.assets.length} asset{group.assets.length === 1 ? "" : "s"}</span></header>
    {!group.assets.length ? <p className="deliverables-missing">No deliverables yet. Create an asset for this timeline item in the content canvas.</p> : <div className="deliverables-assets">{group.assets.map((asset) => <AssetDeliverables key={asset.id} asset={asset} item={item} download={download} downloading={downloading} />)}</div>}
  </section>;
}

function AssetDeliverables({ asset, item, download, downloading }: { asset: Asset; item?: TimelineItem; download: DownloadAction; downloading: string | null }) {
  const version = asset.versions.find((entry) => entry.version === asset.current_version);
  const media = version?.media_items?.length ? version.media_items : version?.media ? [version.media] : [];
  const prefix = `${asset.platform}-${asset.id}-v${asset.current_version}`;
  const archivePath = `/api/assets/${encodeURIComponent(asset.id)}/deliverables/download`;
  const snapshot = asset.timeline_snapshot;
  const changed = !!snapshot && !!item && (["day", "stage", "platform", "asset_type", "objective"] as const).some((field) => snapshot[field] !== item[field]);
  const isScript = /reel|script|video/.test(asset.asset_type);
  return <article className="deliverables-asset">
    <div className="deliverables-asset-heading"><div><div className="row"><Status value={asset.status} /><Badge>Version {asset.current_version}</Badge><span className="small muted">{title(asset.platform)} · {title(asset.asset_type)}</span></div><h4>{version?.hook || `${title(asset.platform)} ${title(asset.asset_type)}`}</h4></div>
      <button className="button secondary small" disabled={!!downloading || !version} onClick={() => void download(archivePath, `${prefix}.zip`, "application/zip")}><Download size={15} />{downloading === archivePath ? "Preparing…" : "Asset ZIP"}</button>
    </div>
    {changed && <p className="small deliverables-snapshot"><strong>Schedule changed.</strong> Originally created for day {snapshot.day} · {title(snapshot.platform)} · {title(snapshot.asset_type)} · {title(snapshot.stage)}: {snapshot.objective}</p>}
    {!version ? <p className="deliverables-missing">The current asset version is unavailable.</p> : <>
      <div className="deliverables-files">
        <div className="deliverables-file"><FileText size={19} /><div><strong>{isScript ? "Script" : "Copy"}</strong><p className="small muted">Hook, {isScript ? "script" : "body"} and call to action · TXT</p></div><button className="button ghost small" onClick={() => saveText([version.hook, version.body, version.cta].filter(Boolean).join("\n\n"), `${prefix}-${isScript ? "script" : "copy"}.txt`)} aria-label={`Download ${isScript ? "script" : "copy"} for ${version.hook || asset.id}`}><Download size={15} />Download</button></div>
        {version.caption && <div className="deliverables-file"><FileText size={19} /><div><strong>Caption</strong><p className="small muted">Platform caption · TXT</p></div><button className="button ghost small" onClick={() => saveText(version.caption!, `${prefix}-caption.txt`)} aria-label={`Download caption for ${version.hook || asset.id}`}><Download size={15} />Download</button></div>}
      </div>
      <details className="deliverables-copy"><summary>Preview {isScript ? "script" : "copy"}</summary><p className="pre-wrap">{[version.hook, version.body, version.cta].filter(Boolean).join("\n\n")}</p>{version.caption && <><strong>Caption</strong><p className="pre-wrap">{version.caption}</p></>}</details>
      <div className="deliverables-media">{media.map((file) => <MediaDeliverable key={file.id} media={file} asset={asset} prefix={prefix} download={download} downloading={downloading} />)}</div>
      {(!media.some((file) => file.kind === "image") || !media.some((file) => file.kind === "voiceover")) && <div className="deliverables-availability">
        {!media.some((file) => file.kind === "image") && <span><ImageIcon size={14} />No image generated</span>}
        {!media.some((file) => file.kind === "voiceover") && <span><Mic size={14} />No voiceover generated</span>}
      </div>}
    </>}
  </article>;
}

function MediaDeliverable({ media, asset, prefix, download, downloading }: { media: Media; asset: Asset; prefix: string; download: DownloadAction; downloading: string | null }) {
  const [unavailable, setUnavailable] = useState(false);
  const url = `/api/assets/${encodeURIComponent(asset.id)}/media/${encodeURIComponent(media.id)}`;
  const path = `${url}?download=true`;
  const isImage = media.kind === "image";
  const isVoice = media.kind === "voiceover";
  const extension = ({ "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/ogg": "ogg", "audio/mp4": "m4a" } as Record<string, string>)[media.mime_type] || "bin";
  return <figure className="deliverables-media-file">
    {unavailable ? <p className="deliverables-missing">Preview unavailable. Try downloading the file or regenerate it in the content canvas.</p> : isImage ? <img src={url} alt={media.alt_text || "Campaign image"} loading="lazy" onError={() => setUnavailable(true)} /> : isVoice ? <audio controls preload="none" src={url} aria-label={`Voiceover for ${title(asset.platform)} asset ${asset.id}`} onError={() => setUnavailable(true)} /> : null}
    <figcaption><strong>{isImage ? "Image" : isVoice ? "Voiceover" : title(media.kind)}</strong>{media.voice && <span className="small muted">{media.voice}</span>}<button className="button secondary small" disabled={!!downloading} onClick={() => void download(path, `${prefix}-${media.kind}-${media.id}.${extension}`)}><Download size={15} />{downloading === path ? "Downloading…" : "Download file"}</button></figcaption>
    {media.script && <div className="deliverables-narration"><details><summary>Narration script</summary><p className="pre-wrap">{media.script}</p></details><button className="button ghost small" onClick={() => saveText(media.script!, `${prefix}-narration-${media.id}.txt`)}><FileText size={15} />Download narration TXT</button></div>}
  </figure>;
}
