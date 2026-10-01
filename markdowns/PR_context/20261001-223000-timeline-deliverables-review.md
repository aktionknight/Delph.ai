# Timeline deliverables, scoped prompts and campaign human review

Parent observed: d1e017b. This record describes the final integrated outcome, including feature work already present in that parent and the remaining working-tree changes. No Git commit was created by Codex for this change; existing staged changes were preserved.

## Scope and implemented changes

Divided implementation between backend workflow, canvas and planning/review frontend agents as explicitly requested. The primary agent integrated types/styles, reviewed contracts, repaired issues discovered live, and verified the connected workflow. A planning agent stopped due to capacity; the canvas agent completed its remaining frontend area.

Content canvas now chooses a social platform and actual scheduled timeline item. Creation validates campaign/item ownership and platform/type compatibility, persists timeline_item_id and an immutable timeline_snapshot, and feeds day/stage/objective into generation. Text, static images and Instagram narration share this mapping. Schedule revisions leave historical asset placement readable and explicitly indicate a changed schedule. Legacy assets remain readable; unmapped legacy content cannot generate media until a replacement is created from a scheduled item.

Added separate platform captions, including distinct Instagram feed captions and Reel script text. Manual edits, custom AI revision prompts and human feedback create fresh immutable versions and evaluations. Caption text participates in claim/format evaluation. Single X posts keep caption empty and use a dedicated response validator for the complete hook/body/CTA plus newline separators within 280 characters. Invalid model output can advance through the existing provider fallback chain.

Static design generation uses evaluated copy, brand sources, creative direction, platform and timeline objective. The Gemini free-only image guard remains unchanged; no paid image calls were made or enabled. Instagram narration uses a dedicated external prompt, exact documented claims, scoped audio completeness, AI evaluation and at most two drafts before synthesis. Narration evaluation and repair history are retained. Edge neural voice selection uses a bounded allowlist; server-default selection also supports configured Gemini TTS without sending an incompatible Edge voice.

Versions retain media_items for simultaneous image and voice attachments while preserving the latest media compatibility field. New media invalidates approval, and approval explicitly acknowledges all retained media. Editing copy removes stale media from the new version but preserves historical binaries/version metadata. Media reads remain authenticated and owner-scoped.

Custom prompts accompany strategy, directions, timeline, copy, image design, narration, experiments, insights and learnings; prompts are limited to 2,000 characters and scoped to their operation. Background jobs preserve prompts and deliverable IDs. Provider instructions explicitly recognize custom_instructions/human_feedback as style/format/focus preferences below grounding, safety and schema constraints. Experiment prompts affect variant copies rather than mutating the approved original.

Campaign section revisions and immutable review records cover brief, strategy, direction, timeline, insights and learnings. Current-revision approval/request-changes controls are available in the section panels and Approvals. Brief/strategy/timeline manual edits, direction selection and custom-prompt regeneration support fine tuning. Edits increment relevant revisions, reject stale submitted review revisions, and retain histories. Planning reviews are optional and do not authorize asset publication. Asset publication still requires evaluation and explicit current-version approval.

## Verification

- Full offline backend suite: 103 passed. Twelve deliverable/review regressions plus three background-job contract checks cover mapping, prompts, section staleness, caption safety, media coexistence/ownership, immutable versions, approval invalidation, narration grounding/repair, voice allowlists, experiment isolation and X boundaries. Existing account, LangGraph, safety and fallback regressions remain passing.
- TypeScript typecheck passed. Production Next.js build passed, including compilation, type checks and static page generation. The restricted build initially failed with worker spawn EPERM; the permitted rerun succeeded.
- Live Instagram caption generation passed on Gemini Flash-Lite. Initial live X/narration failures exposed duplicated X captions and the Reel template's inappropriate audio requirements; dedicated response/prompt/evaluation fixes were implemented and tested.
- Subsequent live X post, narration plan with grounding evaluation, and real Edge MP3 synthesis all passed through Gemini.
- Final Groq probe: all four updated paths passed (Instagram caption, X post, narration plan and Edge synthesis). Only Gemini text quota exhaustion was deliberately simulated; Groq and embedding/TTS calls were real. A real Groq 20B rate limit recovered through 120B during narration evaluation.
- Python compilation and tracked/staged diff whitespace checks passed. .env remains ignored. No credentials were emitted or added to documentation.

## Limitations and next steps

Browser automation could not initialize because the tool environment rejected its sandbox metadata before browser navigation. No visual browser interaction or viewport screenshots were verified; the build, types, responsive layout code and API workflow tests provide the available checks.

Live tests used synthetic sources and no database writes/publication. They verify returned audio bytes, not listening quality, pronunciation or brand fit. Paid Gemini image/speech and Pollinations image output were not tested. Current Gemini image pricing has no free API generation tier (https://ai.google.dev/gemini-api/docs/pricing); enabling paid image usage requires deliberate server configuration. Edge TTS needs network access but no API key. Gemini/Groq text accounts can both exhaust capacity; embedding availability remains independent of text fallback. No additional mandatory API key was introduced.

Existing live MongoDB transactions, R2 binaries and distributed worker behavior were not separately exercised by this feature's live probes. Planning reviews remain optional, media approval still relies on human visual/audio inspection, and real social posting remains outside the MVP. Restart the launcher to reload updated .env model settings. Broader quality fixtures, browser visual QA and distributed quota/job coordination are the next production hardening steps.
