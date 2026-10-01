# Audit: Deployment Configuration Fixes

**Date**: 2026-10-01  
**Commit topic**: deployment-fixes  
**Severity**: Medium

## Review Summary

Reviewed changes for deployment configuration fixes including MongoDB SSL, download endpoints, and production environment setup.

## Findings

### 1. MongoDB SSL Configuration - VERIFIED ✓
**Severity**: Low  
**Evidence**: `apps/api/app/services/store.py:116-123`
- Uses `certifi.where()` for CA bundle location
- Includes `retryWrites=True` and `w='majority'` for reliability
- Standard pattern for pymongo + MongoDB Atlas
**Mitigation**: None needed - follows MongoDB best practices

### 2. Download Endpoints - POTENTIAL ISSUE
**Severity**: Medium  
**Evidence**: `apps/api/app/api/routes.py:893-913`
- Missing rate limiting on download endpoints
- No size validation before starting download
- Could be abused for resource exhaustion
**Mitigation**: Consider adding rate limiting or requiring approval status before download

### 3. CORS Configuration - CONFIGURATION GAP
**Severity**: Low  
**Evidence**: `.env.example:54-58`
- Empty production URLs by default
- No validation that ALLOWED_ORIGINS matches frontend/backend URLs
- Could lead to misconfiguration in production
**Mitigation**: Document that ALLOWED_ORIGINS must be set correctly or CORS will block all requests

### 4. Vercel Build Cache - INFORMATIONAL
**Severity**: None  
**Evidence**: `apps/web/.vercelignore`
- Standard practice for Next.js on Vercel
- No security implications

### 5. Authentication on Download Endpoints - VERIFIED ✓
**Severity**: None  
**Evidence**: `apps/api/app/api/routes.py:894,903`
- Both endpoints use `Depends(auth.user)` 
- Both call `auth.require_owner()` before processing
- Properly scoped to authenticated owner only

### 6. Missing Tests - INCOMPLETE IMPLEMENTATION
**Severity**: Medium  
**Evidence**: Test file `test_exports_downloads.py` expects these endpoints but they were missing
- Tests exist but were failing due to missing implementation
- Need to verify tests pass after this change
**Mitigation**: Run test suite before deploying to production

### 7. Environment Variable Handling - POTENTIAL ISSUE
**Severity**: Low  
**Evidence**: `apps/api/app/services/store.py:117-124`
- MongoDB connection happens at Repository init time (startup)
- If MONGODB_URI is malformed, application fails to start (fail-fast is good)
- No fallback or graceful degradation
**Mitigation**: Current behavior is acceptable - fail-fast on startup prevents runtime surprises

## Security Considerations

1. **Secrets in logs**: MongoDB connection errors could leak partial connection strings to logs - ensure production logs are secured
2. **Download abuse**: No rate limiting on download endpoints - authenticated users could repeatedly download large ZIPs
3. **CORS misconfiguration**: Empty ALLOWED_ORIGINS in .env.example could lead to deployment with no CORS configured

## Not Tested

- Test suite execution (`test_exports_downloads.py`) was not run in this session
- MongoDB SSL connection on actual Render infrastructure not verified
- CORS behavior with production URLs not tested
- Download endpoint streaming performance with large campaigns not benchmarked

## Regression Risk

**Low to Medium**:
- MongoDB connection changes affect ALL database operations - if certifi fails to load, entire app fails to start
- Download endpoints are new - no existing behavior to break
- Environment variable additions are backward compatible (optional)

## Compliance Notes

This is NOT an exhaustive security audit. Changes involve:
- Network communication (MongoDB TLS)
- File downloads (ZIP streaming)
- CORS configuration (cross-origin security)

Recommend security review before production deployment, especially:
- Rate limiting on download endpoints
- MongoDB connection string security in production logs
- CORS configuration validation

## Recommended Actions Before Deploy

1. Run full test suite: `pytest apps/api/tests/test_exports_downloads.py -v`
2. Verify MongoDB connection with actual production MONGODB_URI in staging
3. Test download endpoints with authenticated requests
4. Set ALLOWED_ORIGINS correctly in production environment
5. Monitor MongoDB connection errors in Render logs during first deploy
