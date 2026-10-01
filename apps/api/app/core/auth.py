"""Mongo-backed password accounts and revocable opaque, HttpOnly cookie sessions."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from pymongo.errors import DuplicateKeyError

from ..schemas import Input, Short

COOKIE = "launchpad_session"


class Account(Input):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=12, max_length=128)
    name: Short = "Campaign creator"


class Profile(Input):
    name: Short
    company: str = Field(default="", max_length=200)
    bio: str = Field(default="", max_length=2000)
    timezone: str = Field(default="UTC", max_length=100)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Auth:
    def __init__(self, repository, demo):
        self.repository, self.demo = repository, demo
        self.attempts, self.lock = {}, Lock()

    def require_owner(self, record, user):
        if not self.demo and getattr(record, "data", {}).get("owner_id") != user.get("id"):
            raise HTTPException(404, "Not found.")

    def limit(self, key, maximum=20):
        with self.lock:
            current = monotonic()
            self.attempts = {k: v for k, v in self.attempts.items() if current - v[0] < 60}
            start, count = self.attempts.get(key, (current, 0))
            if count >= maximum:
                raise HTTPException(429, "Too many requests. Retry in a minute.")
            self.attempts[key] = (start, count + 1)

    def user(self, request: Request):
        if self.demo:
            return {"id": "demo", "name": "Local demo", "email": "", "demo": True}
        if not self.repository.mongo:
            raise HTTPException(503, "Set MONGODB_URI to enable accounts and private workspaces.")
        token = request.cookies.get(COOKIE, "")
        session = self.repository.database.sessions.find_one({"_id": digest(token), "expires_at": {"$gt": datetime.now(timezone.utc)}})
        user = self.repository.database.users.find_one({"_id": session["user_id"]}) if session else None
        if not user:
            raise HTTPException(401, "Sign in to your workspace.")
        return {"id": user["_id"], **{k: user.get(k, "") for k in ("email", "name", "company", "bio", "timezone")}, "demo": False}

    def routes(self):
        routes = APIRouter()

        @routes.get("/me")
        def me(request: Request):
            return self.user(request)

        @routes.patch("/me")
        def profile(body: Profile, request: Request):
            user = self.user(request)
            if self.demo:
                raise HTTPException(409, "Profiles require MongoDB account mode.")
            self.repository.database.users.update_one({"_id": user["id"]}, {"$set": body.model_dump()})
            return self.user(request)

        def account(body, request, response, register):
            self.limit((request.client.host if request.client else "unknown", "auth"))
            if self.demo or not self.repository.mongo:
                raise HTTPException(503, "Accounts require MONGODB_URI and DEMO_MODE=false.")
            db = self.repository.database
            email = body.email.strip().lower()
            if register:
                salt = secrets.token_bytes(16)
                hashed = hashlib.scrypt(body.password.encode(), salt=salt, n=16384, r=8, p=1).hex()
                user = {"_id": str(uuid4()), "email": email, "name": body.name, "salt": salt.hex(), "password_hash": hashed, "created_at": datetime.now(timezone.utc)}
                try:
                    db.users.insert_one(user)
                except DuplicateKeyError:
                    raise HTTPException(409, "Unable to register this email. Try signing in.")
            else:
                user = db.users.find_one({"email": email})
                salt = bytes.fromhex(user["salt"]) if user else bytes(16)
                hashed = hashlib.scrypt(body.password.encode(), salt=salt, n=16384, r=8, p=1).hex()
                if not user or not secrets.compare_digest(hashed, user["password_hash"]):
                    raise HTTPException(401, "Email or password is incorrect.")
            token = secrets.token_urlsafe(32)
            db.sessions.insert_one({"_id": digest(token), "user_id": user["_id"], "expires_at": datetime.now(timezone.utc) + timedelta(days=7)})
            response.set_cookie(COOKIE, token, httponly=True, secure=os.getenv("COOKIE_SECURE", "true").lower() == "true", samesite="strict", max_age=604800, path="/")
            return {"id": user["_id"], "name": user["name"], "email": email}

        @routes.post("/auth/register", status_code=201)
        def register(body: Account, request: Request, response: Response):
            return account(body, request, response, True)

        @routes.post("/auth/login")
        def login(body: Account, request: Request, response: Response):
            return account(body, request, response, False)

        @routes.post("/auth/logout")
        def logout(request: Request, response: Response):
            if self.repository.mongo:
                self.repository.database.sessions.delete_one({"_id": digest(request.cookies.get(COOKIE, ""))})
            response.delete_cookie(COOKIE, path="/")
            return {"ok": True}

        return routes
