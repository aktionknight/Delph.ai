"""Persistent Mongo publication worker: scheduled posts, cleanup and hourly metrics.

Run with the repository virtualenv. Requires account-mode .env and stays running.
No external requests are made until a user schedules a version or publishes one.
"""
import os
from pathlib import Path
import sys
import time
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "apps/api"))

def main():
    if os.getenv("DEMO_MODE", "false").lower() == "true" or not os.getenv("MONGODB_URI"):
        print("Social worker requires MONGODB_URI and DEMO_MODE=false.", flush=True)
        return 1
    from app.services.store import Repository
    from app.services.storage import BlobStore
    from app.services.social import SocialAccounts
    from app.services.publishing import SocialPublisher
    from app.agents import AgentSuite
    repository = Repository()
    repository.initialize()
    accounts = SocialAccounts(repository)
    publisher = SocialPublisher(repository, accounts, AgentSuite(), BlobStore(repository.database))
    print("Social worker running: scheduled publications and hourly real metric refresh.", flush=True)
    try:
        while True:
            try:
                publisher.tick()
            except Exception:
                print("Social worker operation failed; state preserved. Check database/provider access.", flush=True)
            time.sleep(30)
    except KeyboardInterrupt:
        return 0
    finally:
        accounts.close()
        repository.close()

if __name__ == "__main__":
    raise SystemExit(main())
