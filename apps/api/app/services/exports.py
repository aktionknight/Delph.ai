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
                  "embedding", "embeddings", "chunks", "vector", "vectors", "embedding_model"}


def public_data(value):
    """Remove internal storage coordinates and credentials from portable artifacts."""
    if isinstance(value, dict):
        return {str(k): public_data(v) for k, v in value.items()
                if str(k).lower() not in PRIVATE_FIELDS
                and not str(k).lower().endswith(("_token", "_secret", "_password", "_api_key"))}
    if isinstance(value, list):
        return [public_data(v) for v in value]
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
    """Full structured state report; audio binaries remain in downloadable ZIPs."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image

    safe = public_data(payload)
    if len(_json(safe)) > MAX_REPORT_TEXT:
        raise HTTPException(413, "Campaign report exceeds the text limit. Use the JSON export for this campaign.")
    campaign = safe["campaign"]
    regular, bold = report_fonts()
    styles = {"body": ParagraphStyle("body", fontName=regular, fontSize=9, leading=13, spaceAfter=6, splitLongWords=True),
              "title": ParagraphStyle("title", fontName=bold, fontSize=26, leading=32, spaceAfter=18),
              "section": ParagraphStyle("section", fontName=bold, fontSize=17, leading=22, textColor=colors.HexColor("#c94828"), spaceAfter=12),
              "label": ParagraphStyle("label", fontName=bold, fontSize=10, leading=14, spaceBefore=7, spaceAfter=5)}
    story = []
    def paragraph(text, style="body"):
        # Bounded paragraph size avoids pathological single-flowable layout cost.
        value = str(text)
        for start in range(0, max(len(value), 1), 4000):
            part = value[start:start + 4000]
            part = "".join(c for c in part if c in "\n\t" or ord(c) >= 32)
            story.append(Paragraph(escape(part).replace("\n", "<br/>"), styles[style]))
    def render(value, depth=0):
        if isinstance(value, dict):
            if not value:
                paragraph("None recorded.")
            for key, child in value.items():
                title = str(key).replace("_", " ").capitalize()
                if isinstance(child, (dict, list)):
                    paragraph(title, "label")
                    render(child, depth + 1)
                else:
                    paragraph(f"{title}: {child if child is not None else 'Not set'}")
        elif isinstance(value, list):
            if not value:
                paragraph("None recorded.")
            for index, child in enumerate(value, 1):
                if isinstance(child, (dict, list)):
                    paragraph(f"Record {index}", "label")
                    render(child, depth + 1)
                else:
                    paragraph(f"{index}. {child}")
        else:
            paragraph(value if value is not None else "Not generated yet.")
    def section(title, value=None):
        story.append(PageBreak())
        paragraph(title, "section")
        if value is not None:
            render(value)

    paragraph("DELPH.AI / CAMPAIGN REPORT", "label")
    paragraph(campaign.get("name", "Campaign"), "title")
    paragraph("Complete campaign context, deliverables, review history and learning.")
    paragraph(f"Exported {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    paragraph(f"Workspace mode: {safe.get('mode', 'unknown')} | Generation: {safe.get('generation', 'unknown')}")
    paragraph("Deterministic generation and simulated metrics are demo data, not real campaign performance." if safe.get("generation") == "deterministic" else "Performance sources are identified in Analytics; generated content requires human review.")
    paragraph("This report includes every recorded asset version. Download Deliverables for current images, audio and copy files. Exporting does not approve or publish content.")
    paragraph("Contents", "label")
    titles = ["Campaign brief", "Brand and source context", "Strategy", "Creative directions", "Campaign timeline", "Deliverables and version history", "Experiments", "Analytics", "Insights and learnings", "Reviews and agent traces", "Additional campaign context"]
    for index, title in enumerate(titles, 1):
        paragraph(f"{index:02d}  {title}")
    brief_keys = ("id", "name", "brief", "goal", "audience", "platforms", "duration_days", "status", "created_at", "generation_mode")
    section(titles[0], {k: campaign[k] for k in brief_keys if k in campaign})
    section(titles[1], safe.get("brand", {}))
    section(titles[2], campaign.get("strategy", "Not generated yet."))
    section(titles[3], {k: campaign.get(k) for k in ("directions", "selected_direction")})
    section(titles[4], {k: campaign.get(k, []) for k in ("timeline", "timeline_history")})
    section(titles[5])
    if not campaign.get("assets"):
        paragraph("No deliverables generated yet.")
    image_total = 0
    raw_assets = {a["id"]: a for a in payload["campaign"].get("assets", [])}
    for index, asset in enumerate(campaign.get("assets", []), 1):
        if index > 1:
            story.append(PageBreak())
        paragraph(f"Asset {index}: {asset.get('platform', '')} / {asset.get('asset_type', '')}", "label")
        render(asset)
        raw = raw_assets[asset["id"]]
        for media in media_items(current(raw)):
            if media.get("kind") != "image":
                continue
            paragraph("Current image preview", "label")
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
                scale = min(480 / width, 420 / height, 1)
                story.append(Image(preview, width=width * scale, height=height * scale))
                story.append(Spacer(1, 10))
            except (StorageError, HTTPException, ValueError, OSError):
                paragraph("Image preview unavailable. The recorded image metadata is retained above; retry its download from Deliverables.")
    section(titles[6], campaign.get("experiments", []))
    section(titles[7], safe.get("analytics", {}))
    section(titles[8], {k: campaign.get(k, []) for k in ("insights", "learnings", "learning_history")})
    section(titles[9], {k: campaign.get(k, []) for k in ("reviews", "trace", "agent_runs")})
    covered = set(brief_keys) | {"strategy", "directions", "selected_direction", "timeline", "timeline_history", "assets", "experiments", "insights", "learnings", "learning_history", "reviews", "trace", "agent_runs"}
    section(titles[10], {k: v for k, v in campaign.items() if k not in covered})
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
