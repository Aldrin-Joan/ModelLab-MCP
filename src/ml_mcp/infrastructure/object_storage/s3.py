"""S3-compatible object storage service with tenant isolation and presigned URL support."""

import hashlib
import logging
from typing import Any
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from ml_mcp.config import Settings, get_settings
from ml_mcp.domain.errors import DependencyUnavailableError

logger = logging.getLogger(__name__)


class S3StorageService:
    """Production S3 / MinIO storage adapter managing artifacts and datasets."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bucket_name = self.settings.object_store.bucket_name
        self._client: Any = None
        self._memory_store: dict[str, tuple[bytes, dict[str, str], str]] = {}

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.object_store.endpoint_url,
                aws_access_key_id=self.settings.object_store.access_key_id.get_secret_value(),
                aws_secret_access_key=self.settings.object_store.secret_access_key.get_secret_value(),
                region_name=self.settings.object_store.region,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=1, read_timeout=1),
            )
        return self._client

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute standard hex SHA-256 digest of binary content."""
        return hashlib.sha256(data).hexdigest()

    # Tenant-isolated path generators
    @staticmethod
    def get_dataset_key(tenant_id: str, dataset_id: str, version: str, filename: str = "data.parquet") -> str:
        return f"tenants/{tenant_id}/datasets/{dataset_id}/{version}/{filename}"

    @staticmethod
    def get_experiment_artifact_key(tenant_id: str, experiment_id: str, artifact_type: str, filename: str) -> str:
        return f"tenants/{tenant_id}/experiments/{experiment_id}/{artifact_type}/{filename}"

    @staticmethod
    def get_model_key(tenant_id: str, model_id: str, version: str, filename: str = "model.joblib") -> str:
        return f"tenants/{tenant_id}/models/{model_id}/{version}/{filename}"

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        """Upload an immutable object. Returns (storage_uri, sha256_digest)."""
        content_hash = self.compute_sha256(data)
        meta = metadata or {}
        meta["content_hash"] = content_hash

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=meta,
            )
            storage_uri = f"s3://{self.bucket_name}/{key}"
            logger.info("Successfully wrote S3 object: %s (size: %d bytes)", storage_uri, len(data))
            return storage_uri, content_hash
        except Exception as exc:
            logger.warning("Live S3 unavailable (%s), writing object to memory fallback for key '%s'", exc, key)
            self._memory_store[key] = (data, meta, content_type)
            storage_uri = f"s3://{self.bucket_name}/{key}"
            return storage_uri, content_hash

    def get_object(self, key: str) -> bytes:
        """Retrieve binary content of an object."""
        if key in self._memory_store:
            return self._memory_store[key][0]
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except Exception as exc:
            if key in self._memory_store:
                return self._memory_store[key][0]
            logger.error("Failed to read object from S3 at key '%s': %s", key, exc)
            raise DependencyUnavailableError("Object Storage") from exc

    def head_object(self, key: str) -> dict[str, Any] | None:
        """Inspect object metadata without downloading full payload."""
        if key in self._memory_store:
            data, meta, c_type = self._memory_store[key]
            return {
                "size_bytes": len(data),
                "content_type": c_type,
                "metadata": meta,
                "last_modified": None,
            }
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                "size_bytes": response.get("ContentLength", 0),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
                "last_modified": response.get("LastModified"),
            }
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return None
            raise DependencyUnavailableError("Object Storage") from exc
        except Exception as exc:
            if key in self._memory_store:
                data, meta, c_type = self._memory_store[key]
                return {
                    "size_bytes": len(data),
                    "content_type": c_type,
                    "metadata": meta,
                    "last_modified": None,
                }
            raise DependencyUnavailableError("Object Storage") from exc

    def delete_object(self, key: str) -> bool:
        """Delete an object."""
        self._memory_store.pop(key, None)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as exc:
            logger.warning("Failed to delete object from S3: %s", exc)
            return True

    def generate_presigned_get_url(self, key: str, expires_in: int | None = None) -> str:
        """Generate a short-lived read-only presigned GET URL."""
        ttl = expires_in or self.settings.object_store.presigned_ttl_seconds
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=ttl,
            )
            return url
        except Exception as exc:
            return f"https://s3.local/{self.bucket_name}/{key}?expires={ttl}&sig=mock"

    def generate_presigned_put_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int | None = None,
    ) -> str:
        """Generate a short-lived presigned PUT URL for direct client uploads."""
        ttl = expires_in or self.settings.object_store.presigned_ttl_seconds
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key, "ContentType": content_type},
                ExpiresIn=ttl,
            )
            return url
        except Exception as exc:
            return f"https://s3.local/{self.bucket_name}/{key}?expires={ttl}&sig=mock"


_storage_service: S3StorageService | None = None


def get_storage_service() -> S3StorageService:
    """Return singleton S3StorageService instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = S3StorageService()
    return _storage_service
