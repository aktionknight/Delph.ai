# Exports, Auth, and Formatting Fixes

## Scope
- Fixed `/export` backend route to correctly generate and return a PDF document instead of JSON.
- Repaired authentication logic for route access and ownership validation to fix failing downloads.
- Excluded internal vector embeddings and chunk metadata from final PDF exports to improve readability.
- Addressed pollinations API updates and Gemini edge cases in prior modifications.

## Architectural Decisions
- Restored `format=json` optional query parameter to support legacy tests and dual-format exporting.
- Defined `PRIVATE_FIELDS` in `exports.py` explicitly to strip internal identifiers and model representations (like vectors and chunks) from the generated artifact, keeping PDF size small and user-focused.
- Corrected FastAPI `Depends(auth.user)` by strongly typing `request: Request` to avoid silent `422 Unprocessable Entity` test failures.

## Next Steps
Continue feature integrations as specified in technical plans.
