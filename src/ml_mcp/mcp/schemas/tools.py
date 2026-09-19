"""Strict Pydantic schemas for MCP tool arguments and responses."""

from typing import Any

from pydantic import BaseModel, Field


# 1. Discovery Schemas
class ListModelsInput(BaseModel):
    pass


class GetModelInput(BaseModel):
    model_id: str = Field(..., description="Unique model identifier, e.g. 'random_forest'")


class ListModelVersionsInput(BaseModel):
    model_id: str = Field(..., description="Unique model identifier")


class ListDatasetsInput(BaseModel):
    project_id: str | None = Field(default=None, description="Optional project filter")


class GetDatasetInput(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")


class ListDatasetVersionsInput(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")


# 2. Dataset Management Schemas
class RegisterDatasetInput(BaseModel):
    project_id: str = Field(..., description="Project ID to register dataset under")
    name: str = Field(..., description="Human-readable dataset name")
    description: str = Field(default="", description="Detailed description")
    format: str = Field(..., description="Format: 'csv', 'parquet', or 'jsonl'")
    data_base64: str = Field(..., description="Base64-encoded dataset file content")
    version: str = Field(default="1.0", description="Semantic dataset version")


class ValidateDatasetInput(BaseModel):
    format: str = Field(..., description="Format: 'csv', 'parquet', or 'jsonl'")
    data_base64: str = Field(..., description="Base64-encoded dataset file content")


class InspectDatasetInput(BaseModel):
    dataset_id: str = Field(..., description="Dataset ID to inspect")
    version: str = Field(default="1.0", description="Dataset version")
    sample_rows: int = Field(default=5, ge=1, le=50, description="Number of preview records to return")


# 3. Experiment Schemas
class CreateExperimentInput(BaseModel):
    project_id: str = Field(..., description="Target project ID")
    dataset_version_id: str = Field(..., description="Registered DatasetVersion ID")
    model_version_id: str = Field(..., description="Registered ModelVersion ID")
    task_type: str = Field(..., description="'binary_classification', 'multiclass_classification', or 'regression'")
    target_column: str = Field(..., description="Name of column to predict")
    feature_columns: list[str] | None = Field(default=None, description="Subset of features to train on")
    primary_metric: str = Field(default="roc_auc", description="Primary optimization metric")
    additional_metrics: list[str] = Field(default_factory=list)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int = Field(default=42)
    idempotency_key: str | None = Field(default=None)


class GetExperimentInput(BaseModel):
    experiment_id: str = Field(..., description="Experiment ID to fetch")


class CancelExperimentInput(BaseModel):
    experiment_id: str = Field(..., description="Experiment ID to cancel")


class ListExperimentsInput(BaseModel):
    project_id: str | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# 4. Results Schemas
class GetExperimentMetricsInput(BaseModel):
    experiment_id: str = Field(..., description="Target experiment ID")
    split: str | None = Field(default=None, description="'train' or 'validation'")


class GetExperimentPredictionsInput(BaseModel):
    experiment_id: str = Field(..., description="Target experiment ID")


class ListExperimentArtifactsInput(BaseModel):
    experiment_id: str = Field(..., description="Target experiment ID")


class ReadExperimentArtifactInput(BaseModel):
    artifact_id: str = Field(..., description="Target artifact ID")


class CompareExperimentsInput(BaseModel):
    experiment_ids: list[str] = Field(..., min_length=2, max_length=10, description="List of experiment IDs to compare")


# 5. Analysis Schemas
class AnalyzeExperimentInput(BaseModel):
    experiment_id: str = Field(..., description="Experiment ID to analyze")


class AnalyzeModelErrorsInput(BaseModel):
    experiment_id: str = Field(..., description="Experiment ID to inspect errors for")


class CheckExperimentValidityInput(BaseModel):
    experiment_id: str = Field(..., description="Experiment ID to validate")
