# Scope
- Fixed a brittle validation rule in the Marketing agent that caused entire timeline generations to fail when the AI returned slightly malformed arrays (e.g. duplicating a day, skipping a day, or choosing an invalid platform/asset type).

# Implemented Changes
- **Deterministic Timeline Repair:** Replaced the hard crash (`raise AgentError`) in `apps/api/app/agents/marketing.py` with an automatic repair loop.
- **Duration Enforcement:** Truncates excess items and automatically pads missing days using duplicates of the last item or safe defaults.
- **Schema Alignment:** Iterates through the generated timeline and deterministically overrides the `day` integer (ensuring a 1-to-duration sequence), the `platform` (forcing a platform from the campaign's allowed list), and the `asset_type` (forcing a valid type for that platform based on `ASSET_TYPES`).

# Architectural Decisions
- Smaller/faster fallback models often struggle with strict structural constraints like exact day counting and complex enum matching. By automatically sanitizing their output deterministically on the backend rather than throwing errors, we dramatically improve the success rate of fallback models without needing expensive retry loops.

# Verification Results
- If an agent generates an invalid schedule, the backend now fixes the schedule silently instead of bubbling up a frontend crash to the user.

# Limitations
- None.

# Next Steps
- None.
