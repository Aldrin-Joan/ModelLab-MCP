"""Scikit-Learn model trainers: Logistic Regression, Random Forest, Linear SVM, and MLP."""

import io
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.svm import LinearSVC, LinearSVR

from ml_mcp.domain.value_objects import TaskType
from ml_mcp.workers.metrics import MetricsCalculator
from ml_mcp.workers.trainers.base import BaseModelTrainer, TrainingResult


class LogisticRegressionTrainer(BaseModelTrainer):
    """Trainer for Logistic Regression."""

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
            "max_iter": hyperparameters.get("max_iter", 200),
            "C": hyperparameters.get("C", 1.0),
            "penalty": hyperparameters.get("penalty", "l2"),
        }
        model = LogisticRegression(**params)
        model.fit(X_tr, y_tr)

        train_pred = model.predict(X_tr)
        train_proba = model.predict_proba(X_tr)
        val_pred = model.predict(X_val)
        val_proba = model.predict_proba(X_val)

        train_metrics = MetricsCalculator.compute_classification_metrics(y_tr, train_pred, train_proba, task_type)
        val_metrics = MetricsCalculator.compute_classification_metrics(y_val, val_pred, val_proba, task_type)

        # Feature importances from coefficients
        feat_imp: dict[str, float] = {}
        if hasattr(model, "coef_"):
            coef = np.abs(model.coef_).mean(axis=0) if model.coef_.ndim > 1 else np.abs(model.coef_)
            feat_imp = {f"feature_{i}": float(v) for i, v in enumerate(coef)}

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


class RandomForestTrainer(BaseModelTrainer):
    """Trainer for Random Forest classification and regression."""

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
            "max_depth": hyperparameters.get("max_depth", 10),
            "min_samples_split": hyperparameters.get("min_samples_split", 2),
            "n_jobs": -1,
        }

        if task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION):
            model = RandomForestClassifier(**params)
            model.fit(X_tr, y_tr)

            train_pred = model.predict(X_tr)
            train_proba = model.predict_proba(X_tr)
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)

            train_metrics = MetricsCalculator.compute_classification_metrics(y_tr, train_pred, train_proba, task_type)
            val_metrics = MetricsCalculator.compute_classification_metrics(y_val, val_pred, val_proba, task_type)
        else:
            model = RandomForestRegressor(**params)
            model.fit(X_tr, y_tr)

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


class LinearSVMTrainer(BaseModelTrainer):
    """Trainer for Linear SVM."""

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
            "C": hyperparameters.get("C", 1.0),
            "max_iter": hyperparameters.get("max_iter", 1000),
        }

        if task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION):
            model = LinearSVC(**params)
            model.fit(X_tr, y_tr)

            train_pred = model.predict(X_tr)
            val_pred = model.predict(X_val)
            train_metrics = MetricsCalculator.compute_classification_metrics(y_tr, train_pred, None, task_type)
            val_metrics = MetricsCalculator.compute_classification_metrics(y_val, val_pred, None, task_type)
            val_proba = None
        else:
            model = LinearSVR(**params)
            model.fit(X_tr, y_tr)

            train_pred = model.predict(X_tr)
            val_pred = model.predict(X_val)
            train_metrics = MetricsCalculator.compute_regression_metrics(y_tr, train_pred)
            val_metrics = MetricsCalculator.compute_regression_metrics(y_val, val_pred)
            val_proba = None

        feat_imp: dict[str, float] = {}
        if hasattr(model, "coef_"):
            coef = np.abs(model.coef_).mean(axis=0) if model.coef_.ndim > 1 else np.abs(model.coef_)
            feat_imp = {f"feature_{i}": float(v) for i, v in enumerate(coef)}

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


class MLPTrainer(BaseModelTrainer):
    """Trainer for Multi-Layer Perceptron (neural network)."""

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
            "alpha": hyperparameters.get("alpha", 0.0001),
            "max_iter": hyperparameters.get("max_iter", 200),
            "hidden_layer_sizes": hyperparameters.get("hidden_layer_sizes", (100,)),
        }

        if task_type in (TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION):
            model = MLPClassifier(**params)
            model.fit(X_tr, y_tr)

            train_pred = model.predict(X_tr)
            train_proba = model.predict_proba(X_tr)
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)

            train_metrics = MetricsCalculator.compute_classification_metrics(y_tr, train_pred, train_proba, task_type)
            val_metrics = MetricsCalculator.compute_classification_metrics(y_val, val_pred, val_proba, task_type)
        else:
            model = MLPRegressor(**params)
            model.fit(X_tr, y_tr)

            train_pred = model.predict(X_tr)
            val_pred = model.predict(X_val)
            val_proba = None

            train_metrics = MetricsCalculator.compute_regression_metrics(y_tr, train_pred)
            val_metrics = MetricsCalculator.compute_regression_metrics(y_val, val_pred)

        bio = io.BytesIO()
        joblib.dump(model, bio)

        return TrainingResult(
            model=model,
            task_type=task_type,
            train_metrics=train_metrics,
            validation_metrics=val_metrics,
            feature_importances={},
            val_predictions=val_pred,
            val_probabilities=val_proba,
            model_artifact_bytes=bio.getvalue(),
        )
