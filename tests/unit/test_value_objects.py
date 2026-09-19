"""Unit tests for domain value objects and validation constraints."""

import pytest
from pydantic import ValidationError
from ml_mcp.domain.value_objects import (
    TaskType,
    ModelFamily,
    SplitStrategy,
    SplitStrategyType,
    EvaluationConfig,
    ResourcePolicy,
    ExperimentSpec,
    ColumnSchema,
    DatasetSchema,
    FeatureType,
)


def test_valid_experiment_spec():
    spec = ExperimentSpec(
        tenant_id="tenant-1",
        project_id="proj-1",
        dataset_version_id="ds-v1",
        model_version_id="mod-v1",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="target",
        feature_columns=["f1", "f2"],
        evaluation_config=EvaluationConfig(primary_metric="roc_auc", additional_metrics=["accuracy", "f1"]),
        created_by="user-1",
    )
    assert spec.split_strategy.strategy == SplitStrategyType.TRAIN_TEST_SPLIT
    assert spec.split_strategy.test_size == 0.2
    assert spec.resource_policy.max_runtime_seconds == 1800


def test_incompatible_metric_rejected():
    with pytest.raises(ValidationError):
        # r2 metric is incompatible with classification
        ExperimentSpec(
            tenant_id="tenant-1",
            project_id="proj-1",
            dataset_version_id="ds-v1",
            model_version_id="mod-v1",
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="target",
            evaluation_config=EvaluationConfig(primary_metric="r2"),
            created_by="user-1",
        )


def test_dataset_schema_duplicate_columns_rejected():
    cols = [
        ColumnSchema(name="age", feature_type=FeatureType.NUMERIC),
        ColumnSchema(name="Age", feature_type=FeatureType.NUMERIC),
    ]
    with pytest.raises(ValidationError):
        DatasetSchema(
            columns=cols,
            row_count=100,
            column_count=2,
            size_bytes=1024,
            content_hash="sha256:abc",
        )
