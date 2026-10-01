# Scope
- Fixed a bug where model provider credit exhaustion (HTTP 403 Forbidden) bypassed the fallback model routing system.
- Adjusted HTTP status handling in both `GeminiProvider` and `GroqProvider`.

# Implemented Changes
- **Gemini Fallback Support:** Added `403` to the list of `recoverable` status codes inside `apps/api/app/core/gemini.py`. Now, if the API returns 403 due to billing/credit exhaustion, the `ProviderError` is marked as recoverable and assigned a `3600` second cooldown. This allows `routing.py` to seamlessly step down to the next model in `GEMINI_FALLBACK_MODELS`.
- **Groq Fallback Support:** Mirrored the same `403` recoverability check in `apps/api/app/core/groq.py` to ensure secondary provider logic gracefully steps down as well.

# Architectural Decisions
- Cooldown was set to 1 hour (3600 seconds) for 403 errors because credit exhaustions are not transient network blips; hitting the same exhausted API key immediately would guarantee another failure.

# Verification Results
- Credit exhaustion (403) is now properly caught, triggering the fallback loop to lower-power models instead of immediately crashing the Timeline or Generation agents.

# Limitations
- None.

# Next Steps
- None.
