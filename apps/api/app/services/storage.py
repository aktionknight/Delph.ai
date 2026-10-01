"""Private binary storage: Mongo GridFS by default, optional S3-compatible R2."""
import io
import os
from uuid import uuid4


class StorageError(Exception):
    pass


class BlobStore:
    def __init__(self, database):
        self.database = database
        self.r2 = os.getenv("OBJECT_STORAGE", "mongo").lower() == "r2"

    def client(self):
        import boto3
        from botocore.config import Config
        required = ["R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
        if not all(os.getenv(k) for k in required):
            raise StorageError("Set R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET, or use OBJECT_STORAGE=mongo.")
        return boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto", config=Config(connect_timeout=10, read_timeout=60, retries={"max_attempts": 2}, signature_version="s3v4"))

    def put(self, raw, owner, name, mime):
        key = f"{owner}/{uuid4()}"
        try:
            if self.r2:
                self.client().put_object(Bucket=os.environ["R2_BUCKET"], Key=key, Body=raw, ContentType=mime)
            else:
                from gridfs import GridFSBucket
                GridFSBucket(self.database).upload_from_stream_with_id(key, name, io.BytesIO(raw), metadata={"owner_id": owner, "mime_type": mime})
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Private object upload failed. Check storage connectivity and credentials.") from exc
        return {"id": str(uuid4()), "key": key, "storage": "r2" if self.r2 else "mongo", "mime_type": mime}

    def read(self, blob, owner):
        if not blob["key"].startswith(owner + "/"):
            raise StorageError("Object does not belong to this workspace.")
        try:
            if blob["storage"] == "r2":
                return self.client().get_object(Bucket=os.environ["R2_BUCKET"], Key=blob["key"])["Body"]
            from gridfs import GridFSBucket
            return GridFSBucket(self.database).open_download_stream(blob["key"])
        except Exception as exc:
            raise StorageError("Private object download failed. Check storage connectivity.") from exc

    def delete(self, blob):
        if blob["storage"] == "r2":
            self.client().delete_object(Bucket=os.environ["R2_BUCKET"], Key=blob["key"])
        else:
            from gridfs import GridFSBucket
            GridFSBucket(self.database).delete(blob["key"])
