"""Optional Groq, Cohere, Pollinations and Edge TTS adapters. Secrets stay server-side."""
import asyncio
import os
from urllib.parse import quote

import httpx

from .gemini import GeminiProvider
from .errors import AgentError
from .groq import GroqProvider
from .hybrid import HybridProvider


def rerank(query, candidates):
    key = os.getenv("COHERE_API_KEY")
    if not key or not candidates:
        return candidates[:4]
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post("https://api.cohere.com/v2/rerank", headers={"Authorization": f"Bearer {key}"}, json={"model": os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5"), "query": query[:8000], "documents": [s["text"] for s in candidates], "top_n": 4})
        if response.status_code != 200:
            raise AgentError(f"Cohere returned HTTP {response.status_code}. Check key, model and quota, or remove COHERE_API_KEY to use embedding retrieval alone.")
        results = response.json()["results"]
        indices = [r["index"] for r in results]
        if not indices or any(type(i) is not int or i < 0 or i >= len(candidates) for i in indices) or len(set(indices)) != len(indices):
            raise ValueError("Invalid rerank indices")
        return [candidates[i] for i in indices]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise AgentError("Cohere reranking failed. Retry or disable the optional reranker.") from exc


def pollinations_image(prompt):
    key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    if not key:
        raise AgentError("Pollinations image generation requires POLLINATIONS_API_KEY in the backend environment.")
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            with client.stream("GET", f"https://gen.pollinations.ai/image/{quote(prompt[:3000], safe='')}", headers={"Authorization": f"Bearer {key}"}, params={"model": os.getenv("POLLINATIONS_IMAGE_MODEL", "flux"), "width": 1024, "height": 1024, "seed": int.from_bytes(os.urandom(4), "big") % 1000000, "nologo": "true"}) as response:
                if response.status_code != 200:
                    raise AgentError(f"Pollinations returned HTTP {response.status_code}. Check connection and parameters.")
                pieces, size = [], 0
                for piece in response.iter_bytes():
                    size += len(piece)
                    if size > 10 * 1024 * 1024:
                        raise AgentError("Generated image exceeds 10 MiB.")
                    pieces.append(piece)
                return b"".join(pieces), response.headers.get("content-type", "").split(";")[0]
    except httpx.HTTPError as exc:
        raise AgentError("Pollinations could not be reached. Retry image generation.") from exc


def edge_voiceover(text, voice=None):
    voice = voice or os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")
    if voice not in {"en-US-JennyNeural", "en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-IN-NeerjaNeural", "en-IN-PrabhatNeural"}:
        raise AgentError("Select a supported Edge TTS voice.")
    async def generate():
        import edge_tts
        pieces, size = [], 0
        async for chunk in edge_tts.Communicate(text, voice, rate="-5%", pitch="+0Hz").stream():
            if chunk["type"] == "audio":
                size += len(chunk["data"])
                if size > 10 * 1024 * 1024:
                    raise AgentError("Generated voiceover exceeds 10 MiB.")
                pieces.append(chunk["data"])
        raw = b"".join(pieces)
        if not raw:
            raise AgentError("Edge TTS returned no audio.")
        return raw
    try:
        return asyncio.run(asyncio.wait_for(generate(), timeout=120))
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError("Edge TTS is unavailable. Retry or configure Gemini speech. Edge TTS is an unofficial service integration.") from exc
