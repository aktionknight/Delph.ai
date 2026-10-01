# Deployment Configuration Fixes

**Date**: 2026-10-01  
**Parent commit**: 6ae8904

## Scope

Fix deployment issues for Render (backend) and Vercel (frontend):
1. Add missing `/deliverables/download` endpoints for campaigns and assets
2. Fix MongoDB SSL/TLS connection errors on Render
3. Add CORS configuration entries for production deployment URLs
4. Add Vercel build cache ignore file

## Implemented Changes

### Backend API (`apps/api/`)

**routes.py** - Added two new GET endpoints:
- `/campaigns/{campaign_id}/deliverables/download` - Downloads all deliverables for a campaign as a ZIP file
- `/assets/{asset_id}/deliverables/download` - Downloads deliverables for a single asset as a ZIP file
- Both endpoints require authentication and use the existing `deliverables_zip` service
- Both return StreamingResponse with proper ZIP content-type and attachment headers

**store.py** - Fixed MongoDB connection for production deployment:
- Added `certifi` import for SSL certificate bundle
- Added `tlsCAFile=certifi.where()` to MongoClient connection parameters
- Added `retryWrites=True` and `w='majority'` for reliability
- This fixes the "SSL handshake failed: tlsv1 alert internal error" on Render

**requirements.txt** - Added dependency:
- `certifi>=2024,<2028` for SSL/TLS certificate validation

### Environment Configuration

**.env.example** - Added production deployment variables:
- `FRONTEND_URL_PRODUCTION` - For Vercel frontend URL
- `BACKEND_URL_PRODUCTION` - For Render backend URL  
- `ALLOWED_ORIGINS` - CORS allowed origins (comma-separated, includes both local and production URLs)

### Frontend (`apps/web/`)

**.vercelignore** - Added to help with build cache issues:
- Ignores `.next` and `node_modules` during Vercel builds
- Helps prevent stale build cache issues

## Architectural Decisions

1. **Download endpoints use streaming**: Large ZIP files are streamed directly from `SpooledTemporaryFile` to avoid memory issues
2. **MongoDB SSL via certifi**: Using Mozilla's CA bundle via `certifi` is the standard approach for Python MongoDB clients in containerized environments
3. **Owner-scoped downloads**: Both download endpoints require authentication and verify ownership before generating ZIP files

## Verification

- Endpoints follow existing auth patterns with `Depends(auth.user)` and `auth.require_owner()`
- Downloads reuse existing `deliverables_zip()` service from `exports.py`
- MongoDB connection parameters match pymongo best practices for Atlas deployments

## Limitations

- MongoDB SSL fix requires `certifi` package to be installed (added to requirements.txt)
- Download endpoints do not support pagination or partial downloads (full ZIP only)
- CORS origins in `.env.example` are empty by default - user must paste actual URLs

## Next Steps

1. Deploy backend to Render with environment variables set
2. Deploy frontend to Vercel with `NEXT_PUBLIC_API_URL` pointing to Render backend
3. Update `.env` locally with production URLs for `ALLOWED_ORIGINS`
4. Test `/deliverables/download` endpoints with authenticated requests
5. Verify MongoDB connection succeeds on Render startup
