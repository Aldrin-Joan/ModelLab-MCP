"""Unit tests for domain errors and sanitation."""

from ml_mcp.domain.errors import (
    ErrorCode,
    ModelNotApprovedError,
    ResourceLimitExceededError,
    ResourceNotFoundError,
)


def test_domain_error_serialization():
    err = ResourceNotFoundError("Dataset", "ds-12345")
    payload = err.to_dict()

    assert payload["error_code"] == ErrorCode.RESOURCE_NOT_FOUND.value
    assert payload["message"] == "Dataset 'ds-12345' was not found"
    assert payload["details"]["resource_type"] == "Dataset"
    assert payload["details"]["resource_id"] == "ds-12345"
    assert err.status_code == 404


def test_resource_limit_exceeded_error():
    err = ResourceLimitExceededError("concurrent_experiments", limit=5, current=6)
    payload = err.to_dict()

    assert payload["error_code"] == ErrorCode.RESOURCE_LIMIT_EXCEEDED.value
    assert payload["details"]["limit"] == 5
    assert payload["details"]["current"] == 6
    assert err.status_code == 429


def test_model_not_approved_error():
    err = ModelNotApprovedError("untrusted_model", "v1.0")
    payload = err.to_dict()

    assert payload["error_code"] == ErrorCode.MODEL_NOT_APPROVED.value
    assert "not approved" in payload["message"]
    assert err.status_code == 403
