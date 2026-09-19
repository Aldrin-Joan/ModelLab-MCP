"""LightGBM model trainer."""

import io
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np

from ml_mcp.domain.value_objects import TaskType
from ml_mcp.workers.metrics import MetricsCalculator
from ml_mcp.workers.trainers.base import BaseModelTrainer, TrainingResult


class LightGBMTrainer(BaseModelTrainer):
    """Trainer for LightGBM gradient boosted trees."""

    def train(
        self,
        X_tr: np.ndarray,
        y_tr: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        task_type: TaskType,
        hyperparameters: dict[str, Any],
        random_seed: int = 42,
    ) -> TrainingResult:
        params = {
            "random_state": random_seed,
            "n_estimators": hyperparameters.get("n_estimators", 100),
            "num_leaves": hyperparameters.get("num_leaves", 31),
            "learning_rate": hyperparameters.get("learning_rate", 0.1),
            "n_jobs": -1,
            "verbose": -1,
        }

        if task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION):
            model = lgb.LGBMClassifier(**params)
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)])

            train_pred = model.predict(X_tr)
            train_proba = model.predict_proba(X_tr)
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)

            train_metrics = MetricsCalculator.compute_classification_metrics(y_tr, train_pred, train_proba, task_type)
            val_metrics = MetricsCalculator.compute_classification_metrics(y_val, val_pred, val_proba, task_type)
        else:
            model = lgb.LGBMRegressor(**params)
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)])

            train_pred = model.predict(X_tr)
            val_pred = model.predict(X_val)
            val_proba = None

            train_metrics = MetricsCalculator.compute_regression_metrics(y_tr, train_pred)
            val_metrics = MetricsCalculator.compute_regression_metrics(y_val, val_pred)

        feat_imp: dict[str, float] = {}
        if hasattr(model, "feature_importances_"):
            feat_imp = {f"feature_{i}": float(v) for i, v in enumerate(model.feature_importances_)}

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
