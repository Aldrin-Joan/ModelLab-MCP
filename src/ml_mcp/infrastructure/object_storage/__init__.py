"""Object storage package."""

from ml_mcp.infrastructure.object_storage.s3 import S3StorageService, get_storage_service

__all__ = ["S3StorageService", "get_storage_service"]
