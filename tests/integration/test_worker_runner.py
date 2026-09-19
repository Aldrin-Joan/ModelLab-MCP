"""Integration test for WorkerRunner."""

import io
from unittest.mock import MagicMock

import pandas as pd
import pytest

from ml_mcp.application.models.service import ModelService
from ml_mcp.domain.value_objects import (
    EvaluationConfig,
    ExperimentSpec,
    ResourcePolicy,
    TaskType,
)
from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.models import (
    DatasetOrm,
    DatasetVersionOrm,
    ExperimentOrm,
    ProjectOrm,
    TenantOrm,
)
from ml_mcp.infrastructure.postgres.session import DatabaseManager
from ml_mcp.workers.runner import WorkerRunner


@pytest.fixture
async def db():
    db_mgr = DatabaseManager()
    db_mgr.initialize(custom_url="sqlite+aiosqlite:///file:runnerdb?mode=memory&cache=shared&uri=true")
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_mgr
    await db_mgr.close()


@pytest.mark.asyncio
async def test_worker_runner_execution(db: DatabaseManager):
    tenant_id = generate_uuid7()
    project_id = generate_uuid7()
    dataset_id = generate_uuid7()
    dsv_id = generate_uuid7()
    exp_id = generate_uuid7()

    # Create mock storage that keeps data in memory dict
    storage_dict: dict[str, bytes] = {}
    mock_storage = MagicMock()

    def mock_put(key, data, **kwargs):
        storage_dict[key] = data
        return f"s3://bucket/{key}", "sha256:hash"

    def mock_get(key):
        return storage_dict[key]

    mock_storage.put_object.side_effect = mock_put
    mock_storage.get_object.side_effect = mock_get
    mock_storage.get_dataset_key.return_value = f"tenants/{tenant_id}/datasets/{dataset_id}/1.0/data.parquet"
    mock_storage.get_experiment_artifact_key.side_effect = lambda tid, eid, atype, fn: f"tenants/{tid}/experiments/{eid}/{atype}/{fn}"

    # Prepare tabular dataset
    df = pd.DataFrame({
        "num1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0] * 5,
        "num2": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0] * 5,
        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1] * 5,
    })
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    storage_dict[mock_storage.get_dataset_key.return_value] = buf.getvalue()

    # Seed models and create DB records
    async with db.session() as sess:
        t = TenantOrm(id=tenant_id, name="Runner Tenant")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Runner Project")
        sess.add_all([t, p])

        model_svc = ModelService(sess)
        await model_svc.seed_catalog()
        rf_model = await model_svc.get_model("random_forest")
        model_version_id = rf_model["versions"][0]["version"]

        # Fetch actual model_version ORM id
        from ml_mcp.infrastructure.postgres.repositories.models import ModelRepository
        m_repo = ModelRepository(sess)
        mv_orm = await m_repo.get_version("random_forest", "1.0.0")
        assert mv_orm is not None

        ds = DatasetOrm(id=dataset_id, tenant_id=tenant_id, project_id=project_id, name="Runner DS", format="parquet")
        dsv = DatasetVersionOrm(
            id=dsv_id,
            dataset_id=dataset_id,
            version="1.0",
            schema_json={"columns": []},
            row_count=len(df),
            column_count=3,
            size_bytes=len(buf.getvalue()),
            content_hash="sha256:ds",
            storage_uri=f"s3://bucket/tenants/{tenant_id}/datasets/{dataset_id}/1.0/data.parquet",
        )
        sess.add_all([ds, dsv])

        spec = ExperimentSpec(
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv_orm.id,
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="target",
            evaluation_config=EvaluationConfig(primary_metric="roc_auc"),
            resource_policy=ResourcePolicy(max_runtime_seconds=60),
            created_by="runner-user",
        )

        exp = ExperimentOrm(
            id=exp_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv_orm.id,
            spec_json=spec.model_dump(),
            status="QUEUED",
            created_by="runner-user",
        )
        sess.add(exp)

    # Execute experiment with WorkerRunner
    async with db.session() as sess:
        runner = WorkerRunner(session=sess, storage_service=mock_storage)
        run_res = await runner.execute_experiment(exp_id, tenant_id)

        assert run_res["status"] == "SUCCEEDED"
        assert "accuracy" in run_res["metrics"]
        assert "model_uri" in run_res["artifacts"]
        assert "predictions_uri" in run_res["artifacts"]

    # Verify final state in DB
    async with db.session() as sess:
        from ml_mcp.infrastructure.postgres.repositories.experiments import ExperimentRepository
        e_repo = ExperimentRepository(sess)
        saved_exp = await e_repo.get_experiment(tenant_id, exp_id)
        assert saved_exp is not None
        assert saved_exp.status == "SUCCEEDED"
        assert len(saved_exp.runs) == 1
        assert saved_exp.runs[0].status == "SUCCEEDED"
        assert len(saved_exp.metrics) > 0
        assert len(saved_exp.artifacts) == 2
