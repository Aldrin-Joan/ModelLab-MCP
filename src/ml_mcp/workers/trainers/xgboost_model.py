"""XGBoost model trainer."""

import io
from typing import Any
import joblib
import numpy as np
import xgboost as xgb
from ml_mcp.domain.value_objects import TaskType
from ml_mcp.workers.metrics import MetricsCalculator
from ml_mcp.workers.trainers.base import BaseModelTrainer, TrainingResult


class XGBoostTrainer(BaseModelTrainer):
    """Trainer for XGBoost gradient boosted trees."""

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
            "max_depth": hyperparameters.get("max_depth", 6),
            "learning_rate": hyperparameters.get("learning_rate", 0.1),
            "subsample": hyperparameters.get("subsample", 1.0),
            "n_jobs": -1,
            "verbosity": 0,
        }

        if task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION):
            model = xgb.XGBClassifier(**params)
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

            train_pred = model.predict(X_tr)
            train_proba = model.predict_proba(X_tr)
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)

            train_metrics = MetricsCalculator.compute_classification_metrics(y_tr, train_pred, train_proba, task_type)
            val_metrics = MetricsCalculator.compute_classification_metrics(y_val, val_pred, val_proba, task_type)
        else:
            model = xgb.XGBRegressor(**params)
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

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
