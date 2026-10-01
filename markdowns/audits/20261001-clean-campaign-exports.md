# Security & Correctness Audit: Campaign Export Cleanup

## Commit Scope Review
Reviewing changes in `apps/api/app/services/exports.py` and `apps/api/app/api/routes.py` concerning the campaign export endpoint (`/campaigns/{id}/export`), `public_data()` sanitization, and ReportLab PDF document layout.

## Flaws, Vulnerabilities & Regressions Reviewed
1. **Embedding Leakage & Data Privacy**:
   - *Risk*: Raw vector embeddings (dense floating-point vectors from Gemini/provider embed models) and internal chunk offsets were previously leaking when exporting brand context or generating PDF reports.
   - *Severity*: Medium. While not credentials, internal embeddings and raw source chunks represent internal vector store data that unnecessarily bloat responses and expose internal chunking boundaries.
   - *Mitigation*: Implemented recursive detection of embedding keys and raw numeric vectors (`is_numeric_vector()`), stripping them from both JSON and PDF export paths.

2. **Report Completeness & Audit Integrity**:
   - *Risk*: Over-simplification could remove required compliance or audit information such as approval decisions, human feedback, or historical claim changes.
   - *Severity*: Medium.
   - *Mitigation*: Retained approval history with explicit decision records, reviewer feedback, and prior version copy strings (`hook`, `body`, `caption`, `narration`, `media script`) in a clean, compact version summary. Verified that all regression checks in `test_exports_downloads.py` pass.

3. **Denial of Service / ReportLab Memory Exhaustion**:
   - *Risk*: Generating PDFs with unbounded paragraph flowables or thousands of page breaks could trigger high CPU/memory usage.
   - *Severity*: Low.
   - *Mitigation*: Paragraph text is partitioned into safe 4000-character segments. Unnecessary page breaks were removed, reducing layout calculation passes and output PDF size.

## Tests Run
- `pytest apps/api/tests/test_exports_downloads.py`: 9/9 passed.
- `pytest apps/api/tests`: 128 passed, 1 external API test skipped/failed (Pollinations 500 error).

## Limitations & Non-claims
- This review does not guarantee that every possible third-party integration property is filtered; only Delph.ai core entities, RAG embeddings, internal storage coordinates, and private credentials are guaranteed to be stripped.
