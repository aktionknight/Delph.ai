# Audit: Production Build Fixes

**Date**: 2026-10-01  
**Commit topic**: production-build-fixes  
**Severity**: Low

## Review Summary

Reviewed fixes for production build errors in frontend TypeScript compilation and missing backend dependencies for PDF generation tests.

## Findings

### 1. TypeScript Badge Tone Fix - VERIFIED ✓
**Severity**: None  
**Evidence**: `apps/web/components/integrations/panel.tsx:42`
- Changed invalid `tone="muted"` to `tone="neutral"`
- Matches Badge component type signature in `ui.tsx:6`
- Correct fix for TypeScript compilation error
**Mitigation**: None needed - standard type correction

### 2. Missing reportlab Dependency - VERIFIED ✓
**Severity**: None  
**Evidence**: `apps/api/requirements.txt:16`
- Added `reportlab>=4.0,<5` for PDF generation
- Required by `exports.py:campaign_pdf()` function (lines 210-333)
- Was causing 6 test failures in GitHub Actions
**Mitigation**: None needed - missing dependency added

### 3. Missing Pillow Dependency - VERIFIED ✓
**Severity**: None  
**Evidence**: `apps/api/requirements.txt:17`
- Added `pillow>=10.0,<12` for image processing
- Required by `exports.py` line 300: `from PIL import Image as PILImage`
- Used for image preview thumbnails in PDF reports
**Mitigation**: None needed - missing dependency added

### 4. Wide Version Range for Pillow - INFORMATIONAL
**Severity**: Low  
**Evidence**: `pillow>=10.0,<12` spans major versions 10 and 11
- Pillow has had security vulnerabilities in the past
- Wide range allows flexibility but may include breaking changes
**Mitigation**: Consider narrowing to `pillow>=10.0,<11` after testing, or pin to specific version in production

### 5. Line Ending Warnings - INFORMATIONAL
**Severity**: None  
**Evidence**: Git warning "LF will be replaced by CRLF"
- Cosmetic warning on Windows
- Does not affect functionality
**Mitigation**: None needed - normal Windows Git behavior

## Security Considerations

1. **reportlab**: Version 4.0+ has no known critical vulnerabilities as of this review
2. **Pillow**: Wide version range (10-12) may include versions with security issues - recommend periodic updates
3. **PDF generation**: User-supplied content is HTML-escaped in `exports.py:233` before rendering to PDF

## Not Tested

- Vercel production build with TypeScript fix not verified (will be tested by CI)
- GitHub Actions test suite with new dependencies not run locally
- PDF export with actual reportlab/pillow installation not tested in this session
- Image thumbnail generation in PDF reports not verified

## Regression Risk

**Very Low**:
- Frontend change is type correction only - no runtime behavior change
- Backend changes are additive (new dependencies) - no code logic changes
- Existing functionality unchanged

## Compliance Notes

This is NOT an exhaustive security audit. Changes involve:
- Third-party dependencies (reportlab, pillow) with known attack surfaces
- PDF generation from user content (already has HTML escaping)

Recommend:
- Monitor security advisories for reportlab and pillow
- Keep dependencies updated with security patches
- Consider pinning exact versions in production deployments

## Recommended Actions Before Deploy

1. Verify Vercel build passes TypeScript compilation
2. Wait for GitHub Actions test results with new dependencies
3. Test PDF export locally: `pytest apps/api/tests/test_exports_downloads.py -v`
4. Review Pillow version range - consider narrowing to `>=10.0,<11`
