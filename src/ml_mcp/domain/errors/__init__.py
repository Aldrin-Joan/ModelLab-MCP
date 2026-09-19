"""Domain errors package."""

from ml_mcp.domain.errors.base import (
    ArtifactAccessDeniedError,
    AuthenticationRequiredError,
    AuthorizationDeniedError,
    DatasetValidationError,
    DependencyUnavailableError,
    DomainError,
    ExperimentAlreadyExistsError,
    ExperimentNotCancellableError,
    InvalidExperimentError,
    ModelNotApprovedError,
    ResourceLimitExceededError,
    ResourceNotFoundError,
    ResourceVersionRevokedError,
    TaskUnavailableError,
)
from ml_mcp.domain.errors.codes import ErrorCode

__all__ = [
    "ErrorCode",
    "DomainError",
    "AuthenticationRequiredError",
    "AuthorizationDeniedError",
    "ResourceNotFoundError",
    "ResourceVersionRevokedError",
    "InvalidExperimentError",
    "DatasetValidationError",
    "ModelNotApprovedError",
    "ExperimentAlreadyExistsError",
    "ExperimentNotCancellableError",
    "TaskUnavailableError",
    "ArtifactAccessDeniedError",
    "ResourceLimitExceededError",
    "DependencyUnavailableError",
]
