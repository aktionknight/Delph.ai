"""Server-side OAuth and platform adapters. Never expose token material in views."""
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, quote
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from pymongo import ReturnDocument

PLATFORMS = {"x", "linkedin"}


def utcnow():
    return datetime.now(timezone.utc)


def iso():
    return utcnow().isoformat()


class SocialError(Exception):
    def __init__(self, message, *, retry_after=0, uncertain=False, status_code=None):
        super().__init__(message)
        self.retry_after, self.uncertain = retry_after, uncertain
        self.status_code = status_code


def cipher():
    try:
        return Fernet(os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"].encode())
    except (KeyError, ValueError):
        raise SocialError("Set OAUTH_TOKEN_ENCRYPTION_KEY to a persistent Fernet key before connecting accounts.")


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken:
        raise SocialError("Stored OAuth credentials could not be decrypted. Restore the encryption key or reconnect.")


def config(platform):
    if platform not in PLATFORMS:
        raise HTTPException(422, "Only X and LinkedIn publishing are supported.")
    prefix = platform.upper()
    client_id, secret = os.getenv(prefix + "_CLIENT_ID"), os.getenv(prefix + "_CLIENT_SECRET")
    redirect = os.getenv(prefix + "_REDIRECT_URI") or os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/") + f"/api/connect/{platform}/callback"
    if not client_id or not secret:
        raise SocialError(f"Set {prefix}_CLIENT_ID and {prefix}_CLIENT_SECRET to connect this platform.")
    parsed = urlsplit(redirect)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
        raise SocialError("OAuth callback must use HTTPS except on localhost.")
    cipher()
    scopes = "tweet.read tweet.write users.read offline.access media.write" if platform == "x" else "openid profile w_member_social"
    if platform == "linkedin" and os.getenv("LINKEDIN_ANALYTICS_ENABLED", "false").lower() == "true":
        scopes += " r_member_postAnalytics"
    return client_id, secret, redirect, scopes


def public_connection(doc):
    return {key: doc.get(key) for key in ("id", "brand_id", "platform", "provider_account_id", "display_name", "status", "expires_at", "scopes", "connected_at")}


class SocialAccounts:
    def __init__(self, repository, client=None):
        self.repository = repository
        self.http = client or httpx.Client(timeout=30, follow_redirects=False)

    @property
    def db(self):
        if not self.repository.mongo:
            raise SocialError("Social connections require MongoDB account mode.")
        return self.repository.database

    def request(self, method, url, *, token=None, publishing=False, **kwargs):
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            response = self.http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise SocialError("Social provider could not be reached. Check the connection before retrying.", uncertain=publishing)
        if response.status_code == 429:
            delay = response.headers.get("retry-after", "60")
            try:
                delay = max(1, min(3600, int(delay)))
            except ValueError:
                delay = 60
            raise SocialError("Social API rate limit reached; publication will retry after backoff.", retry_after=delay)
        if response.status_code >= 500:
            raise SocialError("Social provider is temporarily unavailable.", retry_after=60 if not publishing else 0, uncertain=publishing)
        if response.status_code in {401, 403}:
            raise SocialError("Social API access was denied. Reconnect and check your app products, permissions and API credits.", status_code=response.status_code)
        if not 200 <= response.status_code < 300:
            raise SocialError(f"Social API rejected the request (HTTP {response.status_code}). Check app access and the content format.", status_code=response.status_code)
        return response

    def json(self, response):
        try:
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError:
            raise SocialError("Social provider returned an invalid response.")

    def begin(self, owner, brand_id, platform, session_hash):
        client_id, _, redirect, scopes = config(platform)
        state, verifier, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        self.db.oauth_states.insert_one({"_id": hashlib.sha256(state.encode()).hexdigest(), "owner_id": owner,
            "brand_id": brand_id, "platform": platform, "session_hash": session_hash,
            "binding_hash": hashlib.sha256(binding.encode()).hexdigest(), "verifier": encrypt(verifier),
            "expires_at": utcnow() + timedelta(minutes=10), "redirect_uri": redirect, "scopes": scopes})
        args = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect, "scope": scopes, "state": state}
        if platform == "x":
            args.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode(), code_challenge_method="S256")
        base = "https://x.com/i/oauth2/authorize" if platform == "x" else "https://www.linkedin.com/oauth/v2/authorization"
        return base + "?" + urlencode(args), binding

    def complete(self, platform, state, code, binding):
        config(platform)
        query = {"_id": hashlib.sha256(state.encode()).hexdigest(), "platform": platform,
                 "binding_hash": hashlib.sha256(binding.encode()).hexdigest(), "expires_at": {"$gt": utcnow()}}
        pending = self.db.oauth_states.find_one_and_delete(query)
        if not pending or not self.db.sessions.find_one({"_id": pending["session_hash"], "user_id": pending["owner_id"], "expires_at": {"$gt": utcnow()}}):
            raise SocialError("OAuth session expired or was already used. Sign in and connect again.")
        body = {"grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect_uri"]}
        if platform == "x":
            body["code_verifier"] = decrypt(pending["verifier"])
        tokens = self.token_request(platform, body)
        token = tokens.get("access_token")
        if not token:
            raise SocialError("OAuth provider did not return an access token.")
        url = "https://api.x.com/2/users/me" if platform == "x" else "https://api.linkedin.com/v2/userinfo"
        identity = self.json(self.request("GET", url, token=token))
        identity = identity.get("data", {}) if platform == "x" else identity
        account_id = identity.get("id") if platform == "x" else identity.get("sub")
        if not isinstance(account_id, str) or not account_id:
            raise SocialError("OAuth provider returned no account identity.")
        previous = self.db.connections.find_one({"owner_id": pending["owner_id"], "brand_id": pending["brand_id"], "platform": platform})
        doc = {"_id": previous["_id"] if previous else str(uuid4()), "id": None, "generation": str(uuid4()), "owner_id": pending["owner_id"], "brand_id": pending["brand_id"],
               "platform": platform, "provider_account_id": account_id if platform == "x" else "urn:li:person:" + account_id,
               "display_name": identity.get("name") or identity.get("username") or account_id,
               "status": "active", "connected_at": iso(), "scopes": tokens.get("scope", pending["scopes"]).split(),
               **self.token_fields(tokens)}
        doc["id"] = doc["_id"]
        # Mongo _id stays immutable; a new generation invalidates previously scheduled bindings.
        self.db.connections.replace_one({"owner_id": doc["owner_id"], "brand_id": doc["brand_id"], "platform": platform}, doc, upsert=True)
        return public_connection(doc)

    def token_request(self, platform, body):
        client_id, secret, _, _ = config(platform)
        body = {**body, "client_id": client_id}
        if platform == "x":
            response = self.request("POST", "https://api.x.com/2/oauth2/token", data=body, auth=(client_id, secret))
        else:
            response = self.request("POST", "https://www.linkedin.com/oauth/v2/accessToken", data={**body, "client_secret": secret})
        return self.json(response)

    def token_fields(self, tokens):
        try:
            seconds = int(tokens["expires_in"])
            if not tokens.get("access_token") or seconds <= 0:
                raise ValueError()
            fields = {"access_token": encrypt(tokens["access_token"]), "expires_at": (utcnow() + timedelta(seconds=seconds)).isoformat()}
            if tokens.get("refresh_token"):
                fields["refresh_token"] = encrypt(tokens["refresh_token"])
            return fields
        except (KeyError, ValueError, TypeError):
            raise SocialError("OAuth token response is incomplete; reconnect the account.")

    def connection(self, owner, connection_id):
        doc = self.db.connections.find_one({"_id": connection_id, "owner_id": owner})
        if not doc or doc["status"] != "active":
            raise SocialError("This social account is disconnected. Connect it again and reschedule.")
        return doc

    def access(self, owner, connection_id):
        doc = self.connection(owner, connection_id)
        if datetime.fromisoformat(doc["expires_at"]) > utcnow() + timedelta(minutes=2):
            return doc, decrypt(doc["access_token"])
        lock = str(uuid4())
        locked = self.db.connections.find_one_and_update({"_id": doc["_id"], "owner_id": owner, "status": "active",
            "$or": [{"refresh_lock_until": {"$exists": False}}, {"refresh_lock_until": {"$lte": utcnow()}}]},
            {"$set": {"refresh_lock": lock, "refresh_lock_until": utcnow() + timedelta(seconds=90)}}, return_document=ReturnDocument.AFTER)
        if not locked:
            raise SocialError("Account token is refreshing; retry shortly.", retry_after=5)
        try:
            if not doc.get("refresh_token"):
                self.db.connections.update_one({"_id": doc["_id"], "refresh_lock": lock}, {"$set": {"status": "reconnect_required"}})
                raise SocialError("This provider did not issue a refresh token. Reconnect the account to continue posting.")
            tokens = self.token_request(doc["platform"], {"grant_type": "refresh_token", "refresh_token": decrypt(doc["refresh_token"])})
            fields = self.token_fields(tokens)
            if tokens.get("scope"):
                fields["scopes"] = tokens["scope"].split()
            updated = self.db.connections.update_one({"_id": doc["_id"], "owner_id": owner, "status": "active", "refresh_lock": lock}, {"$set": fields})
            if updated.matched_count != 1:
                raise SocialError("Connection changed while refreshing. Reconnect and reschedule.")
            doc.update(fields)
            return doc, decrypt(doc["access_token"])
        except SocialError as exc:
            if not exc.retry_after:
                self.db.connections.update_one({"_id": doc["_id"], "refresh_lock": lock}, {"$set": {"status": "reconnect_required"}})
            raise
        finally:
            self.db.connections.update_one({"_id": doc["_id"], "refresh_lock": lock}, {"$unset": {"refresh_lock": "", "refresh_lock_until": ""}})

    def linkedin_headers(self):
        return {"LinkedIn-Version": os.getenv("LINKEDIN_API_VERSION", "202609"), "X-Restli-Protocol-Version": "2.0.0"}

    def upload_image(self, connection, token, raw, mime):
        if len(raw) > 5 * 1024 * 1024 or not ((mime == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or (mime == "image/jpeg" and raw.startswith(b"\xff\xd8\xff"))):
            raise SocialError("Social statics must be PNG or JPEG and at most 5 MB.")
        if connection["platform"] == "x":
            if "media.write" not in connection["scopes"]:
                raise SocialError("Reconnect X with media.write permission to publish images.")
            data = self.json(self.request("POST", "https://api.x.com/2/media/upload", token=token,
                json={"media": base64.b64encode(raw).decode(), "media_category": "tweet_image"})).get("data", {})
            if not data.get("id") or data.get("processing_info", {}).get("state", "succeeded") != "succeeded":
                raise SocialError("X image upload is incomplete; retry publication after checking the upload.")
            return data["id"]
        value = self.json(self.request("POST", "https://api.linkedin.com/rest/images", token=token, headers=self.linkedin_headers(),
            params={"action": "initializeUpload"}, json={"initializeUploadRequest": {"owner": connection["provider_account_id"]}})).get("value", {})
        upload = urlsplit(value.get("uploadUrl", ""))
        if upload.scheme != "https" or upload.hostname not in {"www.linkedin.com", "api.linkedin.com"} or upload.username or upload.password:
            raise SocialError("LinkedIn returned an untrusted upload destination.")
        if not value.get("image", "").startswith("urn:li:image:"):
            raise SocialError("LinkedIn returned no image identity.")
        self.request("PUT", value["uploadUrl"], token=token, content=raw, headers={"Content-Type": mime})
        return value["image"]

    def post(self, connection, token, text, *, image_id=None, reply_id=None, alt_text=""):
        if connection["platform"] == "x":
            payload = {"text": text}
            if image_id:
                payload["media"] = {"media_ids": [image_id]}
            if reply_id:
                payload["reply"] = {"in_reply_to_tweet_id": reply_id}
            response = self.request("POST", "https://api.x.com/2/tweets", token=token, publishing=True, json=payload)
            try:
                post_id = self.json(response).get("data", {}).get("id")
            except SocialError:
                raise SocialError("X returned an unreadable publication receipt. Inspect the account before retrying.", uncertain=True)
            if not isinstance(post_id, str) or not post_id.isdigit():
                raise SocialError("X accepted the request without a valid post ID. Inspect the account before retrying.", uncertain=True)
            return post_id
        payload = {"author": connection["provider_account_id"], "commentary": text, "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
        if image_id:
            payload["content"] = {"media": {"id": image_id, "altText": alt_text[:4086]}}
        response = self.request("POST", "https://api.linkedin.com/rest/posts", token=token, publishing=True,
                                headers=self.linkedin_headers(), json=payload)
        post_id = response.headers.get("x-restli-id", "")
        if not post_id.startswith(("urn:li:share:", "urn:li:ugcPost:")):
            raise SocialError("LinkedIn accepted the request without a post ID. Inspect the account before retrying.", uncertain=True)
        return post_id

    def metrics(self, connection, token, post_ids):
        result = {"impressions": None, "clicks": None, "conversions": None, "likes": None, "comments": None, "reposts": None}
        if connection["platform"] == "x":
            try:
                response = self.request("GET", "https://api.x.com/2/tweets", token=token,
                    params={"ids": ",".join(post_ids), "tweet.fields": "public_metrics,organic_metrics,non_public_metrics"})
            except SocialError as exc:
                if exc.status_code not in {400, 403}:
                    raise
                # Older posts or limited app permissions may expose only public metrics.
                response = self.request("GET", "https://api.x.com/2/tweets", token=token,
                    params={"ids": ",".join(post_ids), "tweet.fields": "public_metrics"})
            data = self.json(response)
            if data.get("errors") or len(data.get("data", [])) != len(post_ids):
                raise SocialError("X returned incomplete analytics; the previous snapshot was preserved.")
            for item in data["data"]:
                public = item.get("public_metrics", {})
                private = {**item.get("non_public_metrics", {}), **item.get("organic_metrics", {})}
                fields = {"impressions": private.get("impression_count", public.get("impression_count")), "clicks": private.get("url_link_clicks"),
                    "likes": public.get("like_count"), "comments": public.get("reply_count"), "reposts": public.get("retweet_count")}
                for key, value in fields.items():
                    if isinstance(value, int) and value >= 0:
                        result[key] = (result[key] or 0) + value
            for key, public_key, private_key in (("impressions", "impression_count", "impression_count"), ("clicks", None, "url_link_clicks"),
                    ("likes", "like_count", None), ("comments", "reply_count", None), ("reposts", "retweet_count", None)):
                for item in data["data"]:
                    private = {**item.get("non_public_metrics", {}), **item.get("organic_metrics", {})}
                    value = private.get(private_key, item.get("public_metrics", {}).get(public_key))
                    if not isinstance(value, int) or value < 0:
                        result[key] = None
                        break
            return result
        if "r_member_postAnalytics" not in connection["scopes"]:
            raise SocialError("LinkedIn insights need approved r_member_postAnalytics access. Enable LINKEDIN_ANALYTICS_ENABLED and reconnect after app approval.")
        for query_type, field in (("IMPRESSION", "impressions"), ("LINK_CLICKS", "clicks"), ("REACTION", "likes"), ("COMMENT", "comments"), ("RESHARE", "reposts")):
            total = 0
            supported = True
            for post_id in post_ids:
                # LinkedIn's Rest.li analytics finder uses `ugc` as the discriminator
                # even though the post URN itself is `urn:li:ugcPost:...`.
                kind = "share" if post_id.startswith("urn:li:share:") else "ugc"
                # Preserve the Rest.li finder syntax while percent-encoding the URN.
                # Passing this through httpx `params` would escape the structural syntax.
                query = urlencode({"q": "entity", "entity": f"({kind}:{quote(post_id, safe='')})",
                                   "queryType": query_type, "aggregation": "TOTAL"}, safe="():%")
                url = "https://api.linkedin.com/rest/memberCreatorPostAnalytics?" + query
                try:
                    data = self.json(self.request("GET", url, token=token, headers=self.linkedin_headers()))
                except SocialError as exc:
                    if exc.status_code == 400:
                        supported = False
                        break
                    raise
                elements = data.get("elements")
                if not isinstance(elements, list) or not elements or any(not isinstance(e.get("count"), int) or e["count"] < 0 for e in elements):
                    raise SocialError("LinkedIn returned no complete analytics snapshot; previous data was preserved.")
                total += sum(e["count"] for e in elements)
            result[field] = total if supported else None
        return result

    def close(self):
        self.http.close()
