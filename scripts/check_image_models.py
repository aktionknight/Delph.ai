"""Check image-model metadata with the existing key; never generate billable images."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import httpx


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print(json.dumps({"error": "Set GEMINI_API_KEY in the root .env."}))
        return 1
    primary = os.getenv("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image"
    candidates = list(dict.fromkeys([primary, *os.getenv("GEMINI_IMAGE_FALLBACK_MODELS", "gemini-3.1-flash-lite-image").split(",")]))
    usable = False
    with httpx.Client(timeout=15) as client:
        for model in (candidate.strip() for candidate in candidates[:5] if candidate.strip()):
            try:
                response = client.get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
                                      headers={"x-goog-api-key": key})
                supported = response.status_code == 200 and "generateContent" in response.json().get("supportedGenerationMethods", [])
                usable = usable or supported
                print(json.dumps({"model": model, "http_status": response.status_code,
                                  "generate_content_listed": supported}), flush=True)
            except (httpx.HTTPError, ValueError):
                print(json.dumps({"model": model, "error": "Cannot reach model metadata endpoint."}), flush=True)
    print(json.dumps({"note": "Metadata access does not prove billing eligibility or remaining image quota. No image was generated."}))
    return 0 if usable else 1


if __name__ == "__main__":
    raise SystemExit(main())
