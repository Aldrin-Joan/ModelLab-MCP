"""CatBoost model trainer."""

import io
from typing import Any

import catboost as cb
import joblib
import numpy as np

from ml_mcp.domain.value_objects import TaskType
from ml_mcp.workers.metrics import MetricsCalculator
from ml_mcp.workers.trainers.base import BaseModelTrainer, TrainingResult


class CatBoostTrainer(BaseModelTrainer):
    """Trainer for CatBoost gradient boosted trees."""

    def train(
        self,
        X_tr: np.ndarray,
        y_tr: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        task_type: TaskType,
        hyperparameters: dict[str, Any],
        random_seed: int = 42,
        max_cpu_cores: int | None = None,
    ) -> TrainingResult:
        thread_count = (
            max_cpu_cores if max_cpu_cores is not None else hyperparameters.get("thread_count", -1)
        )
        params = {
            "random_seed": random_seed,
            "iterations": hyperparameters.get("iterations", 100),
            "depth": hyperparameters.get("depth", 6),
            "learning_rate": hyperparameters.get("learning_rate", 0.1),
            "thread_count": thread_count,
            "verbose": False,
            "allow_writing_files": False,
        }

        if task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION):
            model = cb.CatBoostClassifier(**params)
            model.fit(X_tr, y_tr, eval_set=(X_val, y_val), verbose=False)

            train_pred = model.predict(X_tr)
            train_proba = model.predict_proba(X_tr)
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)

            train_metrics = MetricsCalculator.compute_classification_metrics(
                y_tr, train_pred, train_proba, task_type
            )
            val_metrics = MetricsCalculator.compute_classification_metrics(
                y_val, val_pred, val_proba, task_type
            )
        else:
            model = cb.CatBoostRegressor(**params)
            model.fit(X_tr, y_tr, eval_set=(X_val, y_val), verbose=False)

            train_pred = model.predict(X_tr)
            val_pred = model.predict(X_val)
            val_proba = None

            train_metrics = MetricsCalculator.compute_regression_metrics(y_tr, train_pred)
            val_metrics = MetricsCalculator.compute_regression_metrics(y_val, val_pred)

        feat_imp: dict[str, float] = {}
        if hasattr(model, "get_feature_importance"):
            importances = model.get_feature_importance()
            feat_imp = {f"feature_{i}": float(v) for i, v in enumerate(importances)}

        bio = io.BytesIO()
        joblib.dump(model, bio)

        return TrainingResult(
            model=model,
            task_type=task_type,
            train_metrics=train_metrics,
            validation_metrics=val_metrics,
            feature_importances=feat_imp,
            val_predictions=val_pred,
            val_probabilities=val_proba,
            model_artifact_bytes=bio.getvalue(),
        )
