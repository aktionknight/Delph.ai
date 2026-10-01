"""Native Gemini image requests using the same server-side Gemini credential."""
import base64

from .errors import ProviderError
from .routing import models

DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"
IMAGE_FALLBACKS = "gemini-3.1-flash-lite-image"


def generate_image(provider, pool, model, prompt, alt_text):
    def invoke(candidate_model, timeout):
        result = provider.request(candidate_model, "generateContent", {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }, timeout=timeout, retry_transient=False)
        if result.get("promptFeedback", {}).get("blockReason"):
            raise ProviderError("Gemini blocked the image request for safety.", reason="safety", recoverable=False)
        try:
            candidate = result["candidates"][0]
            if candidate.get("finishReason") in {"SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION", "SPII"}:
                raise ProviderError("Gemini blocked the generated image for safety.", reason="safety", recoverable=False)
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Incomplete image")
            inline = next(part["inlineData"] for part in candidate["content"]["parts"]
                          if not part.get("thought") and part.get("inlineData", {}).get("mimeType") in {"image/png", "image/jpeg"})
            if len(inline["data"]) > 14 * 1024 * 1024:
                raise ValueError("Encoded image exceeds limit")
            raw = base64.b64decode(inline["data"], validate=True)
            mime = inline["mimeType"]
            if not raw or len(raw) > 10 * 1024 * 1024:
                raise ValueError("Image exceeds limit")
            if not ((mime == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or
                    (mime == "image/jpeg" and raw.startswith(b"\xff\xd8\xff"))):
                raise ValueError("Invalid image signature")
        except (KeyError, IndexError, ValueError, StopIteration, TypeError) as exc:
            raise ProviderError("Gemini returned incomplete or unsupported image data.", reason="invalid_response") from exc
        return raw, {"kind": "image", "provider": "gemini", "model": candidate_model,
                     "mime_type": mime, "alt_text": alt_text, "usage": result.get("usageMetadata", {}),
                     "requires_human_review": True}
    # Image fallbacks must never inherit the unrelated Gemini text-model chain.
    return pool.run("image", models("GEMINI_IMAGE", "generation", model, IMAGE_FALLBACKS), invoke)
