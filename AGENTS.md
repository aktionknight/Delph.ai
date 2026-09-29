# Repository instructions

## Project scope

Read `markdowns/globals/campaign_launchpad_technical_implementation.md` before implementation. Campaign Launchpad connects every feature through persistent campaign state. Follow its phased MVP priorities; explicitly label deterministic generation and simulated metrics.

## Project markdowns

- `markdowns/globals/` contains user-owned project specifications. Do not add, edit, move, or delete anything there unless the user explicitly requests it.
- Keep implementation context in `markdowns/PR_context/` and reviews in `markdowns/audits/`.

## Mandatory commit documentation

For **every Git commit**, including commits intended for GitHub, add and stage both:

1. A new `markdowns/PR_context/<timestamp>-<short-topic>.md` describing the latest scope, implemented changes, architectural decisions, verification results, limitations, and next steps.
2. A new `markdowns/audits/<timestamp>-<short-topic>.md` reviewing that commit for flaws, vulnerabilities, regressions, and remaining implementations. Include severity, evidence, mitigations, and any tests not run. Do not claim an exhaustive security audit.

Use matching unique filenames for the pair. Include both files in the same commit as the changes they describe. Do not modify old records as a substitute for new ones. Do not put a commit's own hash in its contents; use a topic and parent hash when available. Inspect the staged diff and run relevant checks before committing. Never commit secrets or generated dependencies.

Install the repository hook with `git config core.hooksPath .githooks` after Git initialization. The hook must reject commits missing either newly added record. CI must check every commit in a push or pull request for the same pair.

## Implementation collaboration

Use focused subagents for independently owned areas when the user requests delegation. Agree on API contracts before parallel edits. Do not overwrite another agent's files. Integrate and verify the connected workflow before reporting completion.

Run commands without opening terminal windows. Use noninteractive/background execution; on Windows, any `Start-Process` helper must use `-WindowStyle Hidden` and Python subprocess helpers should use `CREATE_NO_WINDOW`.

## Safety and correctness

- Require evaluation and explicit approval of the current asset version before publication.
- Revisions invalidate approvals; preserve immutable version and approval history.
- Keep secrets server-side. Validate inputs and upload size/type.
- Never present local demo mode as production authentication or simulated metrics as real performance.
- Document incomplete integrations and security gaps honestly.
