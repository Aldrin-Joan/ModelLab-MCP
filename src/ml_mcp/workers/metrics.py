"""Comprehensive evaluation metrics computation engine for classification and regression."""

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    explained_variance_score,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from ml_mcp.domain.value_objects import TaskType


class MetricsCalculator:
    """Calculates all standard ML evaluation metrics without placeholders or approximations."""

    @staticmethod
    def compute_classification_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray | None = None,
        task_type: TaskType = TaskType.BINARY_CLASSIFICATION,
    ) -> dict[str, float | list[list[int]]]:
        """Compute full classification metric suite."""
        metrics: dict[str, float | list[list[int]]] = {}

        metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
        metrics["f1"] = float(f1_score(y_true, y_pred, average="weighted" if task_type == TaskType.MULTICLASS_CLASSIFICATION else "binary", zero_division=0))
        metrics["f1_macro"] = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
        metrics["precision"] = float(precision_score(y_true, y_pred, average="weighted" if task_type == TaskType.MULTICLASS_CLASSIFICATION else "binary", zero_division=0))
        metrics["recall"] = float(recall_score(y_true, y_pred, average="weighted" if task_type == TaskType.MULTICLASS_CLASSIFICATION else "binary", zero_division=0))

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        metrics["confusion_matrix"] = cm.tolist()

        # Probability-based metrics
        if y_proba is not None:
            try:
                if task_type == TaskType.BINARY_CLASSIFICATION:
                    # y_proba can be 1D or 2D
                    proba_pos = y_proba[:, 1] if y_proba.ndim == 2 and y_proba.shape[1] > 1 else y_proba
                    metrics["roc_auc"] = float(roc_auc_score(y_true, proba_pos))
                    metrics["pr_auc"] = float(average_precision_score(y_true, proba_pos))
                    metrics["brier_score"] = float(brier_score_loss(y_true, proba_pos))
                    metrics["log_loss"] = float(log_loss(y_true, y_proba))
                elif task_type == TaskType.MULTICLASS_CLASSIFICATION:
                    metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba, multi_class="ovr"))
                    metrics["log_loss"] = float(log_loss(y_true, y_proba))
            except Exception:
                # Handle edge cases (e.g. single-class batch in fold)
                pass

        return metrics

    @staticmethod
    def compute_regression_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float]:
        """Compute full regression metric suite."""
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        mae = float(mean_absolute_error(y_true, y_pred))
        r2 = float(r2_score(y_true, y_pred))

        metrics: dict[str, float] = {
            "mse": mse,
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
            "explained_variance": float(explained_variance_score(y_true, y_pred)),
        }

        try:
            metrics["mape"] = float(mean_absolute_percentage_error(y_true, y_pred))
        except Exception:
            pass

        return metrics
