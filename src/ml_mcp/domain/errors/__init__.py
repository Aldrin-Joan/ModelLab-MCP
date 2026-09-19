"""Domain errors package."""

from ml_mcp.domain.errors.codes import ErrorCode
from ml_mcp.domain.errors.base import (
    DomainError,
    AuthenticationRequiredError,
    AuthorizationDeniedError,
    ResourceNotFoundError,
    ResourceVersionRevokedError,
    InvalidExperimentError,
    DatasetValidationError,
    ModelNotApprovedError,
    ExperimentAlreadyExistsError,
    ExperimentNotCancellableError,
    TaskUnavailableError,
    ArtifactAccessDeniedError,
    ResourceLimitExceededError,
    DependencyUnavailableError,
)

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
