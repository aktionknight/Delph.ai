# Gemini images: free-only configuration

Parent revision: `eba626b44542bc24e3435d7a91ebc67419a18bd8`. Follow-up to the uncommitted AI/Mongo suite implementation.

## Scope and changes

The user requested Gemini free-tier image generation. Google's current [API pricing](https://ai.google.dev/gemini-api/docs/pricing), checked October 1, 2026, lists image generation as unavailable on the free tier. No functioning free-tier Gemini image model can be supplied under that constraint.

Keep `IMAGE_PROVIDER=gemini`, configure the current `gemini-3.1-flash-image` model, and default `GEMINI_IMAGE_ALLOW_PAID=false` in the environment template and local ignored `.env`. Preserve other credential values. Add a guard that rejects image requests before visual planning, image API calls or version changes while free-only mode is active. Paid calls require an explicit configuration opt-in. No vendor fallback is performed. Update README with this limitation.

## Decisions, verification and limitations

Do not confuse UI access or trial credits with an API free tier. Do not configure an obsolete image model or invoke paid services under a free-only request. The generic paid image integration remains available only after explicit configuration.

All 21 backend tests pass, including a new test proving free-only image generation never calls a text or image provider. No live image request was made. No frontend changes require a new build. No commit is created. The next step is to revisit Google's published tiers if free API image generation becomes available, or obtain user authorization for a different available image-generation arrangement.
