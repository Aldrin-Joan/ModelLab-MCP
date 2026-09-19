"""Unit tests for S3 storage service."""

from unittest.mock import MagicMock

from ml_mcp.infrastructure.object_storage.s3 import S3StorageService


def test_tenant_path_helpers():
    key = S3StorageService.get_dataset_key("t-123", "ds-456", "v1.0", "train.parquet")
    assert key == "tenants/t-123/datasets/ds-456/v1.0/train.parquet"

    artifact_key = S3StorageService.get_experiment_artifact_key("t-123", "exp-789", "predictions", "test_preds.parquet")
    assert artifact_key == "tenants/t-123/experiments/exp-789/predictions/test_preds.parquet"

    model_key = S3StorageService.get_model_key("t-123", "mod-999", "v2.0")
    assert model_key == "tenants/t-123/models/mod-999/v2.0/model.joblib"


def test_sha256_computation():
    data = b"hello model lab"
    digest = S3StorageService.compute_sha256(data)
    assert len(digest) == 64
    assert isinstance(digest, str)


def test_put_and_presigned_urls():
    service = S3StorageService()
    mock_boto = MagicMock()
    mock_boto.generate_presigned_url.return_value = "https://s3.amazonaws.com/test?token=signed"
    service._client = mock_boto

    # Test put_object
    uri, digest = service.put_object("test/path.txt", b"payload", content_type="text/plain")
    assert uri.startswith("s3://")
    mock_boto.put_object.assert_called_once()

    # Test generate_presigned_get_url
    url = service.generate_presigned_get_url("test/path.txt", expires_in=300)
    assert url == "https://s3.amazonaws.com/test?token=signed"
    mock_boto.generate_presigned_url.assert_called_with(
        ClientMethod="get_object",
        Params={"Bucket": service.bucket_name, "Key": "test/path.txt"},
        ExpiresIn=300,
    )
