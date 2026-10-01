"""Owner-scoped aggregate repository with atomic, optimistic multi-record writes."""
from copy import deepcopy
import os

from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from ..models.database import Record, make_engine, make_sessions


class CapacityError(Exception):
    pass


class SQLStore:
    def __init__(self, session, owner):
        self.session, self.owner = session, owner

    def get(self, model, key):
        record = self.session.get(model, key)
        return record if record and record.data.get("owner_id", "demo") == self.owner else None

    def list(self, kind, parent=None):
        query = select(Record).where(Record.kind == kind)
        if parent is not None:
            query = query.where(Record.parent_id == parent)
        return [r for r in self.session.scalars(query) if r.data.get("owner_id", "demo") == self.owner]

    def add(self, record):
        record.data = {**record.data, "owner_id": self.owner}
        self.session.add(record)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()


class MongoStore:
    def __init__(self, database, owner):
        self.database, self.owner, self.loaded, self.original = database, owner, {}, {}

    def get(self, model, key):
        if key in self.loaded:
            return self.loaded[key]
        doc = self.database.records.find_one({"_id": key, "owner_id": self.owner})
        if not doc:
            return None
        record = Record(id=doc["_id"], kind=doc["kind"], parent_id=doc.get("parent_id"), data=doc["data"], revision=doc["revision"])
        self.loaded[key], self.original[key] = record, deepcopy(record.data)
        return record

    def list(self, kind, parent=None):
        query = {"kind": kind, "owner_id": self.owner}
        if parent is not None:
            query["parent_id"] = parent
        return [self.get(Record, doc["_id"]) for doc in self.database.records.find(query, {"_id": 1})]

    def add(self, record):
        record.data = {**record.data, "owner_id": self.owner}
        self.loaded[record.id] = record

    def commit(self):
        # Atlas or a replica set is required. A conflict rolls back the entire workflow mutation.
        if not any(r.id not in self.original or r.data != self.original[r.id] for r in self.loaded.values()):
            return
        # Advance read dependencies so brand changes racing publication conflict.
        changed = list(self.loaded.values())
        with self.database.client.start_session() as session:
            with session.start_transaction():
                for r in changed:
                    revision = r.revision or 0
                    doc = {"_id": r.id, "owner_id": self.owner, "kind": r.kind, "parent_id": r.parent_id, "data": r.data, "revision": revision + 1}
                    from bson import BSON
                    if len(BSON.encode(doc)) > 15 * 1024 * 1024:
                        raise CapacityError("This record reached the MVP history capacity. Export its history and use a new campaign or brand; existing history has been preserved.")
                    if r.id not in self.original:
                        self.database.records.insert_one(doc, session=session)
                    elif self.database.records.replace_one({"_id": r.id, "owner_id": self.owner, "revision": revision}, doc, session=session).matched_count != 1:
                        raise StaleDataError("Aggregate revision conflict")
        for r in changed:
            r.revision = (r.revision or 0) + 1
            self.original[r.id] = deepcopy(r.data)

    def rollback(self):
        self.loaded.clear()
        self.original.clear()


class Repository:
    def __init__(self, url=None):
        self.mongo = url is None and bool(os.getenv("MONGODB_URI"))
        self.client = None
        if self.mongo:
            from pymongo import MongoClient
            self.client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=10000)
            self.database = self.client[os.getenv("MONGODB_DATABASE") or os.getenv("DATABASE_NAME", "campaign_launchpad")]
        else:
            self.engine = None
            if url is not None or os.getenv("DEMO_MODE", "false").lower() == "true":
                self.engine = make_engine(url)
                self.sessions = make_sessions(self.engine)

    def initialize(self):
        if self.mongo:
            self.client.admin.command("ping")
            self.database.records.create_index([("owner_id", 1), ("kind", 1), ("parent_id", 1)])
            self.database.users.create_index("email", unique=True)
            self.database.sessions.create_index("expires_at", expireAfterSeconds=0)
            self.database.jobs.create_index([("owner_id", 1), ("campaign_id", 1)], unique=True, partialFilterExpression={"active": True})

    def open(self, owner):
        if self.mongo:
            return MongoStore(self.database, owner)
        if self.engine is None:
            raise RuntimeError("MongoDB is not configured")
        return SQLStore(self.sessions(), owner)

    def close(self):
        if self.mongo:
            self.client.close()
        elif self.engine is not None:
            self.engine.dispose()
