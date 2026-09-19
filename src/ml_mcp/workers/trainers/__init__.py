"""Model trainers registry and factory."""

from ml_mcp.domain.value_objects import ModelFamily
from ml_mcp.workers.trainers.base import BaseModelTrainer, TrainingResult
from ml_mcp.workers.trainers.sklearn_models import (
    LogisticRegressionTrainer,
    RandomForestTrainer,
    LinearSVMTrainer,
    MLPTrainer,
)
from ml_mcp.workers.trainers.xgboost_model import XGBoostTrainer
from ml_mcp.workers.trainers.lightgbm_model import LightGBMTrainer
from ml_mcp.workers.trainers.catboost_model import CatBoostTrainer


TRAINER_MAP: dict[ModelFamily | str, type[BaseModelTrainer]] = {
    ModelFamily.LOGISTIC_REGRESSION: LogisticRegressionTrainer,
    ModelFamily.LOGISTIC_REGRESSION.value: LogisticRegressionTrainer,
    ModelFamily.RANDOM_FOREST: RandomForestTrainer,
    ModelFamily.RANDOM_FOREST.value: RandomForestTrainer,
    ModelFamily.XGBOOST: XGBoostTrainer,
    ModelFamily.XGBOOST.value: XGBoostTrainer,
    ModelFamily.LIGHTGBM: LightGBMTrainer,
    ModelFamily.LIGHTGBM.value: LightGBMTrainer,
    ModelFamily.CATBOOST: CatBoostTrainer,
    ModelFamily.CATBOOST.value: CatBoostTrainer,
    ModelFamily.LINEAR_SVM: LinearSVMTrainer,
    ModelFamily.LINEAR_SVM.value: LinearSVMTrainer,
    ModelFamily.MLP: MLPTrainer,
    ModelFamily.MLP.value: MLPTrainer,
}


def get_trainer(family: ModelFamily | str) -> BaseModelTrainer:
    """Return concrete trainer instance for a given model family."""
    trainer_cls = TRAINER_MAP.get(family)
    if not trainer_cls:
        raise ValueError(f"No trainer registered for model family '{family}'")
    return trainer_cls()


__all__ = [
    "BaseModelTrainer",
    "TrainingResult",
    "LogisticRegressionTrainer",
    "RandomForestTrainer",
    "LinearSVMTrainer",
    "MLPTrainer",
    "XGBoostTrainer",
    "LightGBMTrainer",
    "CatBoostTrainer",
    "get_trainer",
]
