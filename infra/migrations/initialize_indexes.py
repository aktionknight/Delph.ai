"""Idempotent Mongo index setup using the same contracts as application startup.

Run with the repository virtualenv from any directory. Does not migrate SQLite
demo accounts or rewrite existing campaign/asset history.
"""
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))
load_dotenv(ROOT / ".env")

from app.services.store import Repository


def main():
    repository = Repository()
    try:
        if not repository.mongo:
            raise RuntimeError("Set MONGODB_URI before initializing production indexes.")
        repository.initialize()
        print("MongoDB indexes initialized.")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
