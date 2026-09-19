"""Experiment value objects and specification contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class TaskType(StrEnum):
    """Supported machine learning task types."""

    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION = "regression"


class ModelFamily(StrEnum):
    """Initial approved tabular model families."""

    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    LINEAR_SVM = "linear_svm"
    MLP = "mlp"


class SplitStrategyType(StrEnum):
    """Dataset splitting strategies."""

    TRAIN_TEST_SPLIT = "train_test_split"
    K_FOLD = "k_fold"
    STRATIFIED_K_FOLD = "stratified_k_fold"
    TIME_SERIES_SPLIT = "time_series_split"


class SplitStrategy(BaseModel):
    """Configuration for splitting dataset into training and evaluation partitions."""

    strategy: SplitStrategyType = SplitStrategyType.TRAIN_TEST_SPLIT
    test_size: float = Field(
        default=0.2, ge=0.05, le=0.5, description="Fraction of data reserved for testing"
    )
    n_splits: int = Field(
        default=5, ge=2, le=20, description="Folds for cross-validation strategies"
    )
    shuffle: bool = True
    random_seed: int = Field(default=42, ge=0)


class EvaluationConfig(BaseModel):
    """Evaluation metrics configuration."""

    primary_metric: str = Field(..., description="Target optimization and reporting metric")
    additional_metrics: list[str] = Field(default_factory=list)


class ResourcePolicy(BaseModel):
    """Hardware quotas and execution bounds for worker isolation."""

    max_runtime_seconds: int = Field(default=1800, ge=10, le=7200)
    max_memory_mb: int = Field(default=4096, ge=256, le=32768)
    max_cpu_cores: int = Field(default=2, ge=1, le=16)


class ExperimentStatus(StrEnum):
    """Lifecycle states of an ML experiment."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    ANALYZING = "ANALYZING"
    ANALYSIS_READY = "ANALYSIS_READY"


class ExperimentSpec(BaseModel):
    """Complete, immutable experiment specification defining reproducible execution."""

    tenant_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    dataset_version_id: str = Field(..., min_length=1)
    model_version_id: str = Field(..., min_length=1)
    task_type: TaskType
    target_column: str = Field(..., min_length=1)
    feature_columns: list[str] | None = None
    split_strategy: SplitStrategy = Field(default_factory=SplitStrategy)
    evaluation_config: EvaluationConfig
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    resource_policy: ResourcePolicy = Field(default_factory=ResourcePolicy)
    random_seed: int = Field(default=42, ge=0)
    idempotency_key: str | None = None
    created_by: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_metrics_compatible_with_task(self) -> "ExperimentSpec":
        classification_metrics = {
            "accuracy",
            "f1",
            "f1_macro",
            "f1_weighted",
            "precision",
            "recall",
            "roc_auc",
            "pr_auc",
            "log_loss",
            "brier_score",
        }
        regression_metrics = {"mse", "rmse", "mae", "r2", "mape", "explained_variance"}

        pm = self.evaluation_config.primary_metric.lower()
        if (
            self.task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION)
            and pm in regression_metrics
            and pm not in classification_metrics
        ):
            raise ValueError(f"Metric '{pm}' is not compatible with classification task")
        if (
            self.task_type == TaskType.REGRESSION
            and pm in classification_metrics
            and pm not in regression_metrics
        ):
            raise ValueError(f"Metric '{pm}' is not compatible with regression task")

        return self
