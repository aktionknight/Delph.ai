# Platform content tuning

Scope: make the selected social platform shape AI copy rather than merely identify the destination. Parent at review: d7e87d1. No commit created by this task.

Changes: shared reviewed channel prompts for LinkedIn, Instagram and X are loaded by the creative and evaluator agents. They apply to initial generation, repair, visual plans and narration where applicable. LinkedIn uses professional, approachable language and work relevance; Instagram uses conversational, visual language with format-specific bodies and captions; X uses concise posts and coherent threads. Brand evidence, timeline snapshots and custom human instructions remain attached to generation and review. Canvas displays the selected channel's writing guidance.

Architecture: channel guidance lives in prompts/creative/platform_*.txt and is selected by the existing prompt loader, so Gemini and Groq share identical policy. Tone is assessed by AI, not keyword heuristics. Existing fixed validation still checks factual restrictions and lengths. The evaluator now distinguishes single X post limits from thread paragraph limits; narration retains its audio-only evaluation scope.

Verification: backend suite passes 120 tests; frontend TypeScript check passes. Eleven new offline cases cover agent dispatch across all supported formats, repair/evaluation context, media prompt selection and narration scope. Live synthetic channel checks are recorded in the matching audit. No database writes, publications or paid image generation were performed by these checks.

Limitations/next steps: prompt-based tone quality varies with the model, evidence and human preferences. Existing immutable versions retain their original copy; regenerate to apply channel tuning, then review and approve the new version. Demo generation remains explicitly labeled. No new dependency or API credential is needed. User-owned specification files and unrelated concurrent changes were not edited by this task.
