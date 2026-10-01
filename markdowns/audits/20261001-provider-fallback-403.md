# Security and Quality Audit: Provider Fallback on 403

## Scope
Reviewing the exception handling additions to the Gemini and Groq API providers in `apps/api/app/core/gemini.py` and `apps/api/app/core/groq.py`.

## Findings

1. **Fallback Logic Integrity**
   - **Severity:** Low
   - **Evidence:** Added HTTP 403 to the whitelist of `recoverable` status codes that trigger a model fallback loop in `routing.py`. Also assigned a 3600s cooldown to 403 errors so the exhausted model isn't repeatedly hammered on subsequent requests.
   - **Mitigation:** The logic properly ensures that hard failures like bad JSON validation (400) still crash out, while billing and quota failures (403/429) correctly trigger the failover cascade to `flash-lite`.

## Tests Not Run
- Manual reproduction of a 403 Billing Error from GCP, though the HTTP response mechanics are fully documented by the provider.

## Conclusion
Fixes critical fallback resiliency. Safe for merge.
