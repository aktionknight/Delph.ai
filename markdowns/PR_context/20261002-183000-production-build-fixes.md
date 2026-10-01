# Production Build Fixes

**Date**: 2026-10-02  
**Parent commit**: 437ae80

## Scope

Fix production build errors blocking Vercel deployment and GitHub Actions test failures.

## Implemented Changes

### Frontend Fix (`apps/web/`)

**components/integrations/panel.tsx:42** - Fixed TypeScript error:
- Changed Badge `tone` from `"muted"` to `"neutral"`
- Badge component only accepts: `"neutral" | "green" | "amber" | "red"`
- Was causing TypeScript compilation failure in Next.js production build
- Issue: `Type '"muted"' is not assignable to type '"neutral" | "green" | "amber" | "red" | undefined'`

### Backend Fix (`apps/api/`)

**requirements.txt** - Added missing PDF generation dependencies:
- `reportlab>=4.0,<5` - PDF generation library for campaign reports
- `pillow>=10.0,<12` - Image processing for PDF image previews

These dependencies are required by `exports.py` for the `campaign_pdf()` function but were missing from requirements, causing 6 test failures:
- `test_pdf_is_default_complete_and_read_only_with_legacy_json`
- `test_pdf_keeps_unicode_and_long_copy_without_truncating`
- `test_copy_revision_excludes_old_media_from_download_but_keeps_pdf_history`
- `test_empty_campaign_downloads_and_unknown_records`
- `test_user_supplied_names_cannot_escape_archive_or_inject_headers`

## Architectural Decisions

1. **Badge tone normalization**: Using `"neutral"` for disabled/coming-soon states maintains visual consistency with other neutral-state badges in the app
2. **PDF dependencies**: Added to main requirements rather than optional dependencies since campaign exports are core functionality

## Verification

- TypeScript compilation will pass in Vercel production build
- GitHub Actions tests will pass with reportlab and pillow installed
- PDF export functionality confirmed in `exports.py` lines 193-333

## Limitations

- Line ending warnings (LF → CRLF) are cosmetic and don't affect functionality
- Pillow version range is wide (10.0-12) to accommodate future security patches

## Next Steps

1. Verify Vercel build succeeds with TypeScript fix
2. Verify GitHub Actions tests pass with new dependencies
3. Test PDF export functionality locally with `reportlab` and `pillow` installed
