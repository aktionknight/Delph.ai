# PR Context: Clean Campaign Exports & Strip Embeddings

## Scope
Clean up the campaign export process to ensure no embedding vectors or chunks leak into JSON/PDF exports, and replace the bloated, excessively long PDF report with a structured, executive-level document free of raw debug dumps, full document texts, and repetitive page breaks.

## Implemented Changes
1. **Embedding & Vector Sanitization (`apps/api/app/services/exports.py` & `apps/api/app/api/routes.py`)**:
   - Enhanced `public_data()` with `is_private_key()` and `is_numeric_vector()` to catch and recursively strip any key matching `embedding`, `embeddings`, `vector`, `vectors`, `chunk`, `chunks`, `dense_embedding`, `sparse_embedding`, or `source_chunks`, as well as any raw numeric vector of floats/ints (dimension >= 8).
   - Ensured that `export(format="json")` in `routes.py` sanitizes `brand` via `public_data()`, guaranteeing that brand source document embeddings are not leaked in JSON exports.

2. **Streamlined PDF Campaign Report (`apps/api/app/services/exports.py`)**:
   - Replaced recursive `render()` dumping of raw internal dictionary objects with clean, human-readable section builders.
   - **Brand Context**: Shows brand name, voice, approved claims, and forbidden phrases, with a clean bulleted list of grounding source titles rather than printing tens of thousands of characters of raw source document text.
   - **Timeline**: Displays current active schedule items concisely with a count of revisions instead of dumping full raw `timeline_history` trees.
   - **Deliverables & Assets**: Renders current asset copy (hook, body, script, CTA, caption, media notes), embedded image preview (if present), evaluation status, and approval decisions. Prior versions are summarized in a compact version history list rather than forcing a page break per asset and printing massive nested JSON evaluation trees.
   - **Experiments & Analytics**: Renders high-level KPIs, platform performance breakdown, and hypotheses with clear provenance labels (simulated demo vs. recorded data).
   - **Activity Trace & Reviews**: Summarizes section reviews and displays key milestone events in a clean one-line format, completely omitting raw `agent_runs` LLM token telemetry and attempt arrays.
   - Eliminated excessive `PageBreak` calls across every individual asset and section, producing a compact, elegant 3-6 page report instead of a 50+ page dump.

## Architectural Decisions
- Centralized sanitization in `public_data()` ensures both JSON exports and PDF generation inherit the same privacy and security boundaries.
- Preserved historical version references (such as prior hooks and audio script revisions) in a compact, one-line version history format to maintain auditability without visual bloat.

## Verification Results
- Ran `pytest apps/api/tests/test_exports_downloads.py`: All 9 tests passed (100%).
- Verified that required audit phrases, unicode characters, approval feedback, and historical draft hooks remain verifiable in the generated PDF while drastically reducing page count.
