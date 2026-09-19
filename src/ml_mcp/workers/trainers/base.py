"""Base trainer contract and training result container."""

import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np

from ml_mcp.domain.value_objects import TaskType


@dataclass
class TrainingResult:
    """Artifacts, predictions, and metrics emitted from model training."""

    model: Any
    task_type: TaskType
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    feature_importances: dict[str, float]
    val_predictions: np.ndarray
    val_probabilities: np.ndarray | None
    model_artifact_bytes: bytes

    def serialize_artifact(self) -> bytes:
        """Serialize model object using joblib."""
        if self.model_artifact_bytes:
            return self.model_artifact_bytes
        bio = io.BytesIO()
        joblib.dump(self.model, bio)
        return bio.getvalue()


class BaseModelTrainer(ABC):
    """Abstract base class for all approved tabular model trainers."""

    @abstractmethod
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
        """Execute model training, evaluate metrics, and package artifacts."""
        pass
