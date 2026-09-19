"""Model registry value objects and constraints."""

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field
from ml_mcp.domain.value_objects.experiment import ModelFamily, TaskType


class ApprovalStatus(StrEnum):
    """Approval lifecycle of registered models."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


class HyperparameterConstraint(BaseModel):
    """Schema constraint definition for a model hyperparameter."""

    name: str
    type: str  # "int", "float", "str", "bool"
    default: Any
    min_value: float | int | None = None
    max_value: float | int | None = None
    allowed_values: list[Any] | None = None
    description: str = ""


class ModelMetadata(BaseModel):
    """Immutable model architecture specification in the catalog."""

    model_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    family: ModelFamily
    supported_task_types: list[TaskType]
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    container_image_digest: str = Field(..., description="SHA-256 digest of verified worker container image")
    artifact_digest: str | None = None
    supported_hyperparameters: list[HyperparameterConstraint] = Field(default_factory=list)
    license: str = "Apache-2.0"
    publisher: str = "ModelLab"
