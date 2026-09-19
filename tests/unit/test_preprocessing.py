"""Unit tests for leak-free PreprocessingPipeline."""

import numpy as np
import pandas as pd

from ml_mcp.domain.value_objects import (
    SplitStrategy,
    SplitStrategyType,
    TaskType,
)
from ml_mcp.workers.preprocessing import PreprocessingPipeline


def test_preprocessing_pipeline_leak_free():
    df = pd.DataFrame({
        "num1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "num2": [10.0, 20.0, np.nan, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
        "cat1": ["a", "b", "a", "b", "c", "a", "b", "c", "a", "b"],
        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    })

    prep = PreprocessingPipeline(
        target_column="target",
        task_type=TaskType.BINARY_CLASSIFICATION,
        split_strategy=SplitStrategy(strategy=SplitStrategyType.TRAIN_TEST_SPLIT, test_size=0.2, random_seed=42),
    )

    folds = prep.fit_transform_folds(df)
    assert len(folds) == 1
    X_tr, X_val, y_tr, y_val, transformer = folds[0]

    assert X_tr.shape[0] == 8
    assert X_val.shape[0] == 2
    assert y_tr.shape[0] == 8
    assert y_val.shape[0] == 2
    # No NaNs remaining in transformed arrays
    assert not np.isnan(X_tr).any()
    assert not np.isnan(X_val).any()


def test_kfold_split_strategy():
    df = pd.DataFrame({
        "feature": list(range(20)),
        "target": [0, 1] * 10,
    })

    prep = PreprocessingPipeline(
        target_column="target",
        task_type=TaskType.BINARY_CLASSIFICATION,
        split_strategy=SplitStrategy(strategy=SplitStrategyType.K_FOLD, n_splits=5, random_seed=42),
    )

    folds = prep.fit_transform_folds(df)
    assert len(folds) == 5
    for X_tr, X_val, y_tr, y_val, _ in folds:
        assert X_tr.shape[0] == 16
        assert X_val.shape[0] == 4
