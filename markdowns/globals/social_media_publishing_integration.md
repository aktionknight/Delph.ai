# Automated Social Media Publishing Integration

This document outlines the architecture and implementation plan for integrating automated, real-world posting to X (Twitter), LinkedIn, and Instagram into the Campaign Launchpad.

## 1. Platform API Setup

You must register a developer application for each platform to get your Client IDs and Secrets.

*   **X (formerly Twitter):**
    *   **API:** [X API v2](https://developer.x.com/en/docs/x-api)
    *   **Requirements:** Create a Project in the X Developer Portal. You can use the **Free Tier** (allows 1,500 posts per month).
    *   **Auth:** OAuth 2.0 with PKCE (Scopes: `tweet.write`, `tweet.read`, `users.read`, `offline.access`).
*   **LinkedIn:**
    *   **API:** [LinkedIn Marketing Developer Platform](https://developer.linkedin.com/)
    *   **Requirements:** Create an app and request access to the "Share on LinkedIn" and "Sign In with LinkedIn" products.
    *   **Auth:** OAuth 2.0 (Scopes: `w_member_social` for personal profiles, or `w_organization_social` for company pages, plus `openid`, `profile`).
*   **Instagram:**
    *   **API:** [Instagram Graph API](https://developers.facebook.com/docs/instagram-api/)
    *   **Requirements:** This is the most restrictive. The user *must* have an Instagram Professional/Business account linked to a Facebook Page.
    *   **Auth:** Facebook OAuth 2.0 (Scopes: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`).

## 2. Database Schema Updates (MongoDB)

You need a secure way to store the OAuth tokens for each workspace/brand, and you need to track the publishing status of your assets.

**A. Create a `connections` Collection:**
```json
{
  "workspace_id": "...",
  "platform": "linkedin",
  "provider_account_id": "urn:li:person:12345",
  "access_token": "AQX...",
  "refresh_token": "AQY...",
  "expires_at": "2026-12-01T00:00:00Z",
  "status": "active"
}
```
*(Note: Always encrypt `access_token` and `refresh_token` before saving them to MongoDB at rest).*

**B. Update `content_assets` Statuses:**
Extend the asset state machine lifecycle:
`approved` → `scheduled` → `publishing` → `published` (or `failed`)

## 3. Backend Implementation (FastAPI)

### A. The OAuth Flow
Create routes to handle the OAuth dances for each platform. Libraries like `Authlib` make this much easier in FastAPI.

```python
# apps/api/app/api/auth_routes.py
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    name='linkedin',
    client_id=LINKEDIN_CLIENT_ID,
    client_secret=LINKEDIN_CLIENT_SECRET,
    server_metadata_url='https://www.linkedin.com/oauth/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid profile w_member_social'}
)

@router.get("/connect/linkedin")
async def connect_linkedin(request: Request):
    redirect_uri = "https://your-app.com/api/connect/linkedin/callback"
    return await oauth.linkedin.authorize_redirect(request, redirect_uri)
```

### B. The Publisher Service
Create a `SocialPublisher` service that translates your Campaign Launchpad `AssetVersion` into the specific JSON payload required by each platform.

### C. The Scheduling Worker
Because posts are scheduled for the future (based on the Marketing Timeline), use a background job scheduler.
*   **Recommendation:** Use **APScheduler** or **Celery** with Redis.
*   **The Job:** Every minute, query MongoDB for assets where `status == 'scheduled'` and `scheduled_at <= NOW()`.
*   Pass those assets to the `SocialPublisher`, execute the post, update their status to `published`, and emit a `trace_event` to the campaign timeline.

## 4. Frontend UI Updates (Next.js)

1.  **Integrations Page:** Create a `/settings/integrations` page where users can click "Connect" buttons for X, LinkedIn, and Instagram. Display a green badge when the OAuth token is successfully stored.
2.  **Asset Editor & Approval Flow:** 
    *   Once an asset is marked as `approved`, show a new UI module: **"Ready to Publish"**.
    *   Provide a date/time picker to set the `scheduled_at` field.
    *   Add a **"Schedule Post"** button that updates the asset status in MongoDB.
3.  **Live Status:** In the Campaign Canvas, update the asset card badges to reflect if a post is `Scheduled for Tomorrow at 9AM`, `Published`, or if it `Failed`.

## Important Pitfalls to Watch Out For

*   **Token Expiration:** OAuth access tokens expire. You *must* implement logic to use the `refresh_token` to get a new access token before publishing, or the background job will fail.
*   **Media Uploads:** Posting text is a single API call. Posting images/video to X or LinkedIn is a **multi-step process**: (1) Register the upload, (2) Upload the binary bytes to a specific URL, (3) Attach the returned media ID to the final post creation call.
*   **Rate Limits:** Implement basic exponential backoff in your background worker in case a platform's API is temporarily unavailable (HTTP 503/429).
