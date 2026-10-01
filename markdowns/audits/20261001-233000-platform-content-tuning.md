# Review: platform content tuning

Review scope: channel prompt selection, generation and repair instructions, evaluator channel and format rules, canvas hints and live-check wiring. Parent at review: d7e87d1. This is a focused correctness review, not an exhaustive security audit.

- Low — Prompt adherence is probabilistic. Evidence: tone rules are model instructions, not deterministic style decisions. Mitigation: evaluator checks platform_fit with actionable repair feedback and current-version human approval remains mandatory. Optional emojis/hashtags are not required for a passing evaluation.
- Low — Historical content keeps its original platform treatment. Evidence: this task changes future generation and repairs rather than persisted immutable versions. Mitigation: regenerate and explicitly approve new versions; no silent rewriting of approved content.
- Corrected — X thread evaluation previously stated a 280-character joined-copy limit for X posts without distinguishing threads. Evidence: evaluator instructions now explicitly apply the joined limit only to single posts and paragraph limits to threads.
- Verified — Reviewed platform policy is selected only from an allowlist; user payload values cannot choose arbitrary prompt filesystem paths. Brand context, selected platform, custom instructions and immutable timeline snapshot survive draft, repair and evaluation dispatch.

Checks: 120 backend tests passed; frontend typecheck passed; git diff --check passed. Eleven new offline regression cases use fixtures and do not establish model quality on their own. Four live synthetic checks passed: LinkedIn post, Instagram Reel with separate caption, X post and X thread, each followed by AI channel/grounding evaluation. Generation used gemini-3.1-flash-lite with no simulated quota exhaustion. Initial restricted-network live calls failed connectivity and were rerun with approved network access. No fresh Groq live probe was performed for this change; both providers use the same tested runtime prompt loader.

Not run: browser interaction (browser tooling unavailable in this session), paid image generation, production database writes or publication, broad performance/quality benchmarking. No new keys, dependencies, publication routes or approval bypasses were introduced. Existing unrelated changes in the workspace remain outside this review.
