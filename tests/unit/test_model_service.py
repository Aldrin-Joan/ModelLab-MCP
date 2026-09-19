"""Unit tests for ModelService and catalog seeding."""

import pytest

from ml_mcp.application.models.service import ModelService
from ml_mcp.infrastructure.postgres.base import Base
from ml_mcp.infrastructure.postgres.session import DatabaseManager


@pytest.fixture
async def db():
    db_mgr = DatabaseManager()
    db_mgr.initialize(
        custom_url="sqlite+aiosqlite:///file:modeldb?mode=memory&cache=shared&uri=true"
    )
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_mgr
    await db_mgr.close()


@pytest.mark.asyncio
async def test_seed_and_list_models(db: DatabaseManager):
    async with db.session() as sess:
        service = ModelService(sess)
        await service.seed_catalog()

    async with db.session() as sess:
        service = ModelService(sess)
        models = await service.list_models()
        assert len(models) == 7

        model_ids = {m["model_id"] for m in models}
        expected = {
            "logistic_regression",
            "random_forest",
            "xgboost",
            "lightgbm",
            "catboost",
            "linear_svm",
            "mlp",
        }
        assert expected == model_ids

        # Get specific model
        rf = await service.get_model("random_forest")
        assert rf["name"] == "Random Forest"
        assert len(rf["versions"]) == 1
        assert "binary_classification" in rf["versions"][0]["supported_task_types"]

        # Validate hyperparameters
        valid_v = await service.validate_model_for_experiment(
            model_id="random_forest",
            version="1.0.0",
            task_type="binary_classification",
            hyperparameters={"n_estimators": 200, "max_depth": 15},
        )
        assert valid_v.model_id == "random_forest"

        # Out-of-bounds hyperparameter should raise ValueError
        with pytest.raises(ValueError) as exc:
            await service.validate_model_for_experiment(
                model_id="random_forest",
                version="1.0.0",
                task_type="binary_classification",
                hyperparameters={"n_estimators": 5000},  # Max allowed is 1000
            )
        assert "maximum" in str(exc.value)
