# Scoped review: free-only Gemini images

Parent revision: `eba626b44542bc24e3435d7a91ebc67419a18bd8`. This is not an exhaustive security audit.

## Findings

- **Blocking external limitation:** Current Gemini image APIs have no free tier according to [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing). Image generation must remain disabled under the user's free-only requirement. The README and runtime error disclose this explicitly.
- **Low, configuration risk:** An operator can explicitly set `GEMINI_IMAGE_ALLOW_PAID=true`. Default and local configuration are false; the application rejects requests before provider calls unless that opt-in is present. It does not silently select Pollinations or another service.
- **Low, future availability risk:** Model names and pricing change. The selected current model remains configurable; published availability needs verification before changing the free-only policy.

## Verification and tests not run

21 backend tests pass. The added guard test fails if any text/image model request occurs while free-only mode is active. Local environment edits preserve unrelated credentials and are ignored by Git. No live API request or billing/quota check was performed, because no supported free-tier image API is documented. No changes to frontend code or user-owned specifications are included. Remaining feature limitation is unavailable free-tier image generation itself.
