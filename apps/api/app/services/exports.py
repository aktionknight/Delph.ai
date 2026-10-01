"""Private, read-only campaign reports and current-version deliverable bundles."""
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from html import escape
import io
import json
from pathlib import Path
import re
from tempfile import SpooledTemporaryFile
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException

from .storage import StorageError

MAX_EXPORT_BYTES = 100 * 1024 * 1024
MAX_MEDIA_BYTES = 25 * 1024 * 1024
MAX_REPORT_TEXT = 12 * 1024 * 1024
MAX_EXPORT_FILES = 5000
MIME_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
                   "image/gif": ".gif", "audio/mpeg": ".mp3", "audio/wav": ".wav",
                   "audio/x-wav": ".wav", "audio/ogg": ".ogg", "video/mp4": ".mp4"}
PRIVATE_FIELDS = {"key", "storage", "blob", "owner_id", "password", "password_hash",
                  "access_token", "refresh_token", "token", "client_secret", "api_key",
                  "authorization", "credentials", "cookie", "signed_url", "presigned_url",
                  "embedding", "embeddings", "chunks", "vector", "vectors", "embedding_model",
                  "dense_embedding", "sparse_embedding", "source_chunks"}


def is_private_key(key: str) -> bool:
    k = str(key).lower()
    if k in PRIVATE_FIELDS:
        return True
    return any(term in k for term in ("embedding", "vector", "chunk", "_token", "_secret", "_password", "_api_key"))


def is_numeric_vector(val) -> bool:
    """Detect raw embedding / numeric vectors."""
    return isinstance(val, (list, tuple)) and len(val) >= 8 and all(isinstance(x, (int, float)) for x in val)


def public_data(value):
    """Remove internal storage coordinates, credentials, and embeddings from portable artifacts."""
    if isinstance(value, dict):
        return {str(k): public_data(v) for k, v in value.items()
                if not is_private_key(k) and not is_numeric_vector(v)}
    if isinstance(value, list):
        if is_numeric_vector(value):
            return []
        return [public_data(v) for v in value if not is_numeric_vector(v)]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        parts = urlsplit(value)
        if any(term in parts.query.lower() for term in ("signature=", "token=", "credential=", "api_key=")):
            return "[private signed URL omitted]"
    return value


def slug(value, fallback="item"):
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value)).strip("-_")[:70] or fallback


def identity(value):
    # Preserve uniqueness even when legacy IDs contain path separators or long values.
    return f"{slug(value)[:38]}-{sha256(str(value).encode()).hexdigest()[:10]}"


def current(asset):
    version = next((v for v in reversed(asset.get("versions", []))
                    if v.get("version") == asset.get("current_version")), None)
    if version is None:
        raise HTTPException(409, "An asset has no matching current version. Repair it before exporting.")
    return version


def media_items(version):
    return version.get("media_items") or ([version["media"]] if version.get("media") else [])


def media_filename(media, index=1):
    return f"{slug(media.get('kind', 'media'))}-{index}{MIME_EXTENSIONS.get(media.get('mime_type'), '.bin')}"


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _text_files(asset, version):
    copy = [f"# {asset.get('platform', '')} / {asset.get('asset_type', '')}",
            f"Version: {asset['current_version']} | Status: {asset.get('status', 'draft')}",
            "Exporting does not approve or publish this asset."]
    for field in ("hook", "body", "cta", "caption"):
        copy.extend((f"\n## {field.title()}", str(version.get(field, ""))))
    yield "copy.md", "copy", "text/markdown", "\n\n".join(copy).encode("utf-8")
    yield "content.json", "metadata", "application/json", _json(public_data(version))
    if version.get("caption"):
        yield "caption.txt", "caption", "text/plain", str(version["caption"]).encode("utf-8")
    script = version.get("script") or (version.get("body") if asset.get("asset_type") in {"reel", "video", "script"} else None)
    if script:
        yield "script.txt", "script", "text/plain", str(script).encode("utf-8")
    if version.get("narration"):
        yield "narration.txt", "narration", "text/plain", str(version["narration"]).encode("utf-8")
    for index, media in enumerate(media_items(version), 1):
        if media.get("script"):
            yield f"{slug(media.get('kind', 'media'))}-{index}-script.txt", "narration", "text/plain", str(media["script"]).encode("utf-8")


def deliverables_manifest(campaign):
    groups = []
    active = {}
    for item in campaign.get("timeline", []):
        group = {"mapping": "active", "timeline_item_id": item["id"],
                 "timeline_item": public_data(item), "assets": []}
        active[item["id"]] = group
        groups.append(group)
    historical = {}
    unmapped = None
    for asset in campaign.get("assets", []):
        version = current(asset)
        item_id = asset.get("timeline_item_id") or version.get("timeline_item_id")
        snapshot = asset.get("timeline_snapshot") or version.get("timeline_snapshot")
        group = active.get(item_id)
        if group is None and (item_id or snapshot):
            history_key = str(item_id or snapshot.get("id") or asset["id"])
            if history_key not in historical:
                historical[history_key] = {"mapping": "historical", "timeline_item_id": item_id,
                                           "timeline_item": public_data(snapshot), "assets": []}
                groups.append(historical[history_key])
            group = historical[history_key]
        if group is None:
            if unmapped is None:
                unmapped = {"mapping": "unmapped", "timeline_item_id": None, "timeline_item": None, "assets": []}
                groups.append(unmapped)
            group = unmapped
        day = (group["timeline_item"] or {}).get("day", "unscheduled")
        folder = f"{group['mapping']}/day-{slug(day)}-{identity(item_id or 'unmapped')}/{slug(asset.get('platform', 'asset'))}-{identity(asset['id'])}-v{slug(asset['current_version'])}"
        files = [{"name": name, "path": f"{folder}/{name}", "kind": kind, "mime_type": mime}
                 for name, kind, mime, _ in _text_files(asset, version)]
        for index, media in enumerate(media_items(version), 1):
            name = media_filename(media, index)
            files.append({"name": name, "path": f"{folder}/{name}", "kind": media.get("kind", "media"),
                          "mime_type": media.get("mime_type", "application/octet-stream"), "media_id": media.get("id")})
        group["assets"].append({"id": asset["id"], "platform": asset.get("platform"),
            "asset_type": asset.get("asset_type"), "status": asset.get("status"),
            "current_version": asset["current_version"], "generation_mode": version.get("generation_mode", campaign.get("generation_mode")),
            "timeline_snapshot": public_data(snapshot), "folder": folder, "files": files})
    return {"schema_version": 1, "campaign_id": campaign["id"], "campaign_name": campaign.get("name", "Campaign"),
            "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "current_versions", "groups": groups}


def read_binary(blobs, media, owner, maximum=MAX_MEDIA_BYTES):
    if not media.get("key") or not media.get("storage"):
        raise StorageError("A deliverable binary is unavailable. Regenerate its media before downloading.")
    stream = blobs.read(media, owner)
    try:
        data = bytearray()
        while True:
            chunk = stream.read(min(65536, maximum + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > maximum:
                raise HTTPException(413, "A deliverable exceeds the download size limit. Download a smaller asset bundle.")
        if not data:
            raise StorageError("A deliverable binary is empty. Regenerate its media before downloading.")
        return bytes(data)
    except (StorageError, HTTPException):
        raise
    except Exception as exc:
        raise StorageError("A deliverable binary could not be read. Retry the download after checking storage.") from exc
    finally:
        stream.close()


def deliverables_zip(campaign, blobs, owner):
    manifest = deliverables_manifest(campaign)
    assets = {asset["id"]: asset for asset in campaign.get("assets", [])}
    count = 1 + sum(len(a["files"]) for g in manifest["groups"] for a in g["assets"])
    if count > MAX_EXPORT_FILES:
        raise HTTPException(413, "Too many files for one bundle. Download individual asset bundles.")
    output = SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b")
    total = 0
    try:
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            def write(path, data):
                nonlocal total
                total += len(data)
                if total > MAX_EXPORT_BYTES:
                    raise HTTPException(413, "Campaign bundle exceeds 100 MB. Download individual asset bundles.")
                archive.writestr(path, data)
            write("manifest.json", _json(manifest))
            for group in manifest["groups"]:
                for entry in group["assets"]:
                    asset = assets[entry["id"]]
                    version = current(asset)
                    for name, _, _, data in _text_files(asset, version):
                        write(f"{entry['folder']}/{name}", data)
                    for index, media in enumerate(media_items(version), 1):
                        write(f"{entry['folder']}/{media_filename(media, index)}", read_binary(blobs, media, owner))
        output.seek(0)
        return output
    except Exception:
        output.close()
        raise


@lru_cache(maxsize=1)
def report_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    pairs = [(Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
             (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
             (Path(reportlab.__file__).parent / "fonts/Vera.ttf", Path(reportlab.__file__).parent / "fonts/VeraBd.ttf")]
    for regular, bold in pairs:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("CampaignRegular", str(regular)))
            pdfmetrics.registerFont(TTFont("CampaignBold", str(bold)))
            pdfmetrics.registerFontFamily("CampaignRegular", normal="CampaignRegular", bold="CampaignBold", italic="CampaignRegular", boldItalic="CampaignBold")
            return "CampaignRegular", "CampaignBold"
    return "Helvetica", "Helvetica-Bold"


def campaign_pdf(payload, blobs=None, owner=None):
    """Clean, structured campaign report; audio binaries remain in downloadable ZIPs."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image

    safe = public_data(payload)
    if len(_json(safe)) > MAX_REPORT_TEXT:
        raise HTTPException(413, "Campaign report exceeds the text limit. Use the JSON export for this campaign.")
    campaign = safe.get("campaign", {})
    brand = safe.get("brand", {})
    strategy = campaign.get("strategy") or {}
    analytics = safe.get("analytics") or {}
    regular, bold = report_fonts()

    styles = {
        "title": ParagraphStyle("title", fontName=bold, fontSize=22, leading=26, textColor=colors.HexColor("#1a1a1a"), spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", fontName=regular, fontSize=9, leading=13, textColor=colors.HexColor("#666666"), spaceAfter=12),
        "section_heading": ParagraphStyle("section_heading", fontName=bold, fontSize=13, leading=17, textColor=colors.HexColor("#c94828"), spaceBefore=14, spaceAfter=8, keepWithNext=True),
        "item_heading": ParagraphStyle("item_heading", fontName=bold, fontSize=10, leading=14, textColor=colors.HexColor("#222222"), spaceBefore=8, spaceAfter=3, keepWithNext=True),
        "label": ParagraphStyle("label", fontName=bold, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"), spaceBefore=4, spaceAfter=1, keepWithNext=True),
        "body": ParagraphStyle("body", fontName=regular, fontSize=9, leading=13, textColor=colors.HexColor("#222222"), spaceAfter=4, splitLongWords=True),
        "body_muted": ParagraphStyle("body_muted", fontName=regular, fontSize=8, leading=12, textColor=colors.HexColor("#666666"), spaceAfter=4, splitLongWords=True),
        "bullet": ParagraphStyle("bullet", fontName=regular, fontSize=8.5, leading=12, textColor=colors.HexColor("#222222"), spaceAfter=2, leftIndent=12, splitLongWords=True),
    }

    story = []

    def p(text, style="body"):
        if text is None:
            return
        val = str(text)
        for start in range(0, max(len(val), 1), 4000):
            chunk = val[start:start + 4000]
            chunk = "".join(c for c in chunk if c in "\n\t" or ord(c) >= 32)
            story.append(Paragraph(escape(chunk).replace("\n", "<br/>"), styles[style]))

    # Title & Metadata Header
    p("DELPH.AI / CAMPAIGN REPORT", "label")
    p(campaign.get("name", "Campaign"), "title")
    p(f"Complete campaign context, deliverables, review history and learning. | Exported {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "subtitle")

    mode_text = f"Workspace mode: {safe.get('mode', 'authenticated')} | Generation: {safe.get('generation', 'gemini')} | Status: {campaign.get('status', 'draft')}"
    p(mode_text, "body_muted")
    if safe.get("generation") == "deterministic" or safe.get("mode") == "local-demo" or analytics.get("is_demo"):
        p("Deterministic generation and simulated metrics are demo data, not real campaign performance.", "body_muted")
    else:
        p("Performance sources are identified in Analytics; generated content requires human review.", "body_muted")
    p("This report includes campaign context, current deliverables, version and approval history, strategy, and learnings. Exporting does not approve or publish content.", "body_muted")
    story.append(Spacer(1, 8))

    # 1. Campaign Brief & Goals
    p("Campaign Brief", "section_heading")
    p(f"Goal: {campaign.get('goal', 'Not set')}", "body")
    p(f"Target Audience: {campaign.get('audience', 'Not set')}", "body")
    platforms = ", ".join(campaign.get("platforms", [])) or "None specified"
    p(f"Target Platforms: {platforms} | Duration: {campaign.get('duration_days', 14)} days", "body")
    if campaign.get("brief"):
        p("Brief Description:", "label")
        p(campaign["brief"], "body")

    # 2. Brand Context
    p("Brand Context", "section_heading")
    p(f"Brand: {brand.get('name', 'Brand')} | Voice: {brand.get('voice', 'Not set')}", "body")
    if brand.get("description"):
        p(f"Description: {brand['description']}", "body")
    if brand.get("approved_claims"):
        p("Approved Claims:", "label")
        for claim in brand["approved_claims"]:
            p(f"• {claim}", "bullet")
    if brand.get("forbidden_phrases"):
        p("Forbidden Phrases:", "label")
        for phrase in brand["forbidden_phrases"]:
            p(f"• {phrase}", "bullet")
    sources = brand.get("sources", [])
    if sources:
        p("Grounding Sources:", "label")
        for s in sources:
            source_name = s.get("name") or "Source"
            source_type = s.get("source_type", "document")
            p(f"• {source_name} ({source_type})", "bullet")

    # 3. Strategy & Creative Direction
    p("Campaign Strategy & Creative Direction", "section_heading")
    if strategy and isinstance(strategy, dict):
        if strategy.get("positioning"):
            p("Positioning Statement:", "label")
            p(strategy["positioning"], "body")
        if strategy.get("core_message"):
            p("Core Message:", "label")
            p(strategy["core_message"], "body")
        if strategy.get("content_pillars"):
            p("Content Pillars:", "label")
            for idx, pillar in enumerate(strategy["content_pillars"], 1):
                p(f"{idx}. {pillar}", "bullet")
        if strategy.get("creative_directions"):
            selected_id = campaign.get("selected_direction")
            for d in strategy["creative_directions"]:
                is_selected = d.get("id") == selected_id
                tag = " [SELECTED DIRECTION]" if is_selected else ""
                p(f"Creative Direction: {d.get('name', 'Direction')}{tag}", "item_heading")
                p(d.get("description", ""), "body")
                if d.get("rationale"):
                    p(f"Why this works: {d['rationale']}", "body_muted")
    else:
        p("Strategy not generated yet.", "body_muted")

    # 4. Campaign Timeline
    p("Campaign Timeline Schedule", "section_heading")
    timeline = campaign.get("timeline", [])
    if timeline:
        for item in timeline:
            day_str = f"Day {item.get('day', 1)}"
            meta = f"{item.get('stage', '').title()} · {item.get('platform', '').title()} · {item.get('asset_type', '').title()}"
            p(f"• {day_str} ({meta}): {item.get('objective', '')}", "bullet")
    else:
        p("No timeline schedule generated yet.", "body_muted")
    if campaign.get("timeline_history"):
        p(f"Timeline schedule revisions: {len(campaign['timeline_history'])} prior version(s) recorded.", "body_muted")

    # 5. Deliverables & Content Assets
    story.append(PageBreak())
    p("Deliverables, Content Assets & Approval History", "section_heading")
    assets = campaign.get("assets", [])
    if not assets:
        p("No deliverables generated yet.", "body_muted")

    image_total = 0
    raw_assets = {a["id"]: a for a in payload.get("campaign", {}).get("assets", [])}
    for index, asset in enumerate(assets, 1):
        status_tag = asset.get("status", "draft").upper()
        p(f"Asset {index}: {str(asset.get('platform', '')).upper()} / {str(asset.get('asset_type', '')).upper()} (v{asset.get('current_version', 1)}) — Status: {status_tag}", "item_heading")

        versions = asset.get("versions", [])
        curr_ver = next((v for v in reversed(versions) if v.get("version") == asset.get("current_version")), None) or (versions[-1] if versions else {})

        if curr_ver.get("hook"):
            p(f"Hook: {curr_ver['hook']}", "body")
        if curr_ver.get("body"):
            p(f"Body: {curr_ver['body']}", "body")
        if curr_ver.get("script") and curr_ver.get("script") != curr_ver.get("body"):
            p(f"Script: {curr_ver['script']}", "body")
        if curr_ver.get("cta"):
            p(f"Call to Action: {curr_ver['cta']}", "body")
        if curr_ver.get("caption"):
            p(f"Caption: {curr_ver['caption']}", "body")
        if curr_ver.get("narration"):
            p(f"Narration: {curr_ver['narration']}", "body")
        for m in media_items(curr_ver):
            if m.get("script") and m.get("script") != curr_ver.get("script"):
                p(f"Media script ({m.get('kind', 'media')}): {m['script']}", "body")

        approvals = asset.get("approvals", [])
        if approvals:
            for app in approvals:
                dec = app.get("decision", "reviewed")
                ver = app.get("version", asset.get("current_version"))
                fb = app.get("feedback") or ""
                p(f"Approval: {dec.title()} for version {ver} — Feedback: \"{fb}\"", "body_muted")

        eval_data = curr_ver.get("evaluation")
        if isinstance(eval_data, dict):
            passed = eval_data.get("passed")
            eval_status = "Passed AI Evaluation" if passed else "Needs Review"
            issues = eval_data.get("issues", [])
            issues_str = f" | Issues: {', '.join(str(i) for i in issues)}" if issues else ""
            p(f"AI Evaluation: {eval_status}{issues_str}", "body_muted")

        prior_versions = [v for v in versions if v.get("version") != asset.get("current_version")]
        if prior_versions:
            p("Version History:", "label")
            for pv in prior_versions:
                v_num = pv.get("version", "?")
                parts = []
                if pv.get("hook"): parts.append(f'Hook: "{pv["hook"]}"')
                if pv.get("body"): parts.append(f'Body: "{pv["body"]}"')
                if pv.get("script"): parts.append(f'Script: "{pv["script"]}"')
                if pv.get("caption"): parts.append(f'Caption: "{pv["caption"]}"')
                if pv.get("narration"): parts.append(f'Narration: "{pv["narration"]}"')
                for m in media_items(pv):
                    if m.get("script"): parts.append(f'Media script ({m.get("kind", "media")}): "{m["script"]}"')
                parts_str = " | ".join(parts) if parts else "Draft revision"
                p(f"• v{v_num}: {parts_str}", "bullet")

        raw = raw_assets.get(asset["id"])
        if raw:
            for media in media_items(current(raw)):
                if media.get("kind") != "image":
                    continue
                p("Current Image Preview:", "label")
                try:
                    if blobs is None or image_total >= MAX_EXPORT_BYTES:
                        raise StorageError("Preview budget unavailable.")
                    binary = read_binary(blobs, media, owner, min(MAX_MEDIA_BYTES, MAX_EXPORT_BYTES - image_total))
                    image_total += len(binary)
                    from PIL import Image as PILImage
                    with PILImage.open(io.BytesIO(binary)) as picture:
                        if picture.width * picture.height > 16_000_000:
                            raise ValueError("Image exceeds preview pixel budget.")
                        picture.thumbnail((1200, 1200))
                        preview = io.BytesIO()
                        picture.convert("RGB").save(preview, format="JPEG", quality=85)
                        width, height = picture.size
                    preview.seek(0)
                    scale = min(480 / width, 360 / height, 1)
                    story.append(Image(preview, width=width * scale, height=height * scale))
                    story.append(Spacer(1, 8))
                except Exception:
                    p("Image preview unavailable; downloadable in Deliverables bundle.", "body_muted")
        story.append(Spacer(1, 6))

    # 6. Experiments & Variants
    experiments = campaign.get("experiments", [])
    if experiments:
        p("Campaign Experiments & Variant Testing", "section_heading")
        for exp in experiments:
            prov = "Simulated metrics" if exp.get("is_demo") else "Recorded results"
            p(f"Experiment: {exp.get('name', 'Experiment')} (Variable: {exp.get('variable', 'hook')}) — {prov}", "item_heading")
            for var in exp.get("variants", []):
                hook = var.get("hook", "Variant")
                stats = f"Impressions: {var.get('impressions', 0):,} | Clicks: {var.get('clicks', 0):,} | CTR: {var.get('ctr', 0)}% | Conversions: {var.get('conversions', 0)}"
                p(f"• Variant {var.get('label', '')}: \"{hook}\" — {stats}", "bullet")

    # 7. Analytics & Performance
    p("Analytics & Performance", "section_heading")
    analytics_prov = analytics.get("provenance") or ("Simulated metrics · not real performance" if analytics.get("is_demo") else "Recorded performance")
    p(f"Source: {analytics_prov}", "body_muted")
    p(f"Key Metrics: Impressions: {analytics.get('impressions', 0):,} | Clicks: {analytics.get('clicks', 0):,} | Conversions: {analytics.get('conversions', 0)} | CTR: {analytics.get('ctr', 0)}", "body")
    if analytics.get("platforms"):
        p("Platform Performance Breakdown:", "label")
        for plat in analytics["platforms"]:
            p(f"• {plat.get('platform', '').title()}: {plat.get('impressions', 0):,} impressions, {plat.get('clicks', 0):,} clicks, {plat.get('conversions', 0)} conversions", "bullet")
    if analytics.get("observations"):
        p("Performance Observations:", "label")
        for obs in analytics["observations"]:
            p(f"• {obs}", "bullet")

    # 8. Insights & Learnings
    p("Campaign Insights & Learnings", "section_heading")
    insights = campaign.get("insights", [])
    if insights:
        p("Insights:", "label")
        for ins in insights:
            p(f"• {ins}", "bullet")
    learnings = campaign.get("learnings", [])
    if learnings:
        p("Hypotheses & Learnings:", "label")
        for lr in learnings:
            conf = f" (Confidence: {int(lr['confidence'] * 100)}%)" if "confidence" in lr else ""
            ev = f" — Evidence: {lr.get('evidence', '')}" if lr.get("evidence") else ""
            p(f"• {lr.get('statement', '')}{conf}{ev}", "bullet")
    if not insights and not learnings:
        p("No learnings or insights recorded yet.", "body_muted")

    # 9. Activity Trace & Planning Reviews
    p("Activity Trace & Planning Reviews", "section_heading")
    reviews = campaign.get("reviews", {})
    if isinstance(reviews, dict) and reviews:
        p("Section Reviews:", "label")
        for sec_name, rev in reviews.items():
            if isinstance(rev, dict):
                p(f"• {sec_name.title()} Review: Status: {rev.get('status', 'pending')} | Notes: {rev.get('notes', 'None')}", "bullet")
    trace = campaign.get("trace", [])
    if trace:
        p(f"Activity Trace Log (Total events: {len(trace)}):", "label")
        key_events = trace[-20:] if len(trace) > 20 else trace
        for ev in key_events:
            ts = str(ev.get("timestamp", ""))[:19].replace("T", " ")
            p(f"• {ts} [{ev.get('event_type', 'event')}] {ev.get('message', '')} ({ev.get('status', 'ok')})", "bullet")

    output = io.BytesIO()
    def page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dddddd"))
        canvas.line(42, 37, A4[0] - 42, 37)
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(42, 24, "Delph.ai | Private campaign report")
        canvas.drawRightString(A4[0] - 42, 24, f"Page {document.page}")
        canvas.restoreState()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42,
                                 bottomMargin=52, title=campaign.get("name", "Campaign"), author="Delph.ai")
    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    output.seek(0)
    return output
