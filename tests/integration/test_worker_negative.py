"""Integration tests verifying WorkerRunner negative paths and error state transitions."""

import asyncio
import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ml_mcp.application.models.service import ModelService
from ml_mcp.domain.errors import ResourceLimitExceededError
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
from ml_mcp.infrastructure.postgres.repositories.experiments import ExperimentRepository
from ml_mcp.infrastructure.postgres.repositories.models import ModelRepository
from ml_mcp.infrastructure.postgres.session import DatabaseManager
from ml_mcp.workers.runner import WorkerRunner
from ml_mcp.workers.sandbox import WorkerSandbox


@pytest.fixture
async def db():
    db_mgr = DatabaseManager()
    db_mgr.initialize(
        custom_url="sqlite+aiosqlite:///file:runner_neg_db?mode=memory&cache=shared&uri=true"
    )
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_mgr
    await db_mgr.close()


@pytest.mark.asyncio
async def test_worker_nonexistent_experiment_raises(db: DatabaseManager):
    """Verify executing a non-existent experiment raises ValueError."""
    async with db.session() as sess:
        runner = WorkerRunner(session=sess)
        with pytest.raises(ValueError) as exc:
            await runner.execute_experiment("nonexistent-exp-id", "tenant-123")
        assert "not found" in str(exc.value)


@pytest.mark.asyncio
async def test_worker_missing_dataset_transitions_to_failed(db: DatabaseManager):
    """Verify that if dataset version is missing, experiment transitions to FAILED."""
    tenant_id = generate_uuid7()
    project_id = generate_uuid7()
    exp_id = generate_uuid7()

    async with db.session() as sess:
        t = TenantOrm(id=tenant_id, name="Tenant Neg")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Project Neg")
        sess.add_all([t, p])

        model_svc = ModelService(sess)
        await model_svc.seed_catalog()
        m_repo = ModelRepository(sess)
        mv = await m_repo.get_version("random_forest", "1.0.0")
        assert mv is not None

        # Spec pointing to non-existent dataset version
        spec = ExperimentSpec(
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id="nonexistent-dsv-id",
            model_version_id=mv.id,
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="target",
            evaluation_config=EvaluationConfig(primary_metric="accuracy"),
            created_by="test-user",
        )
        exp = ExperimentOrm(
            id=exp_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id="nonexistent-dsv-id",
            model_version_id=mv.id,
            spec_json=spec.model_dump(),
            status="QUEUED",
            created_by="test-user",
        )
        sess.add(exp)

    async with db.session() as sess:
        runner = WorkerRunner(session=sess)
        with pytest.raises(ValueError) as exc:
            await runner.execute_experiment(exp_id, tenant_id)
        assert "not found" in str(exc.value).lower()

    # Verify experiment transitioned to FAILED
    async with db.session() as sess:
        e_repo = ExperimentRepository(sess)
        saved_exp = await e_repo.get_experiment(tenant_id, exp_id)
        assert saved_exp is not None
        assert saved_exp.status == "FAILED"
        assert len(saved_exp.runs) == 1
        assert saved_exp.runs[0].status == "FAILED"
        assert "not found" in saved_exp.runs[0].failure_reason.lower()


@pytest.mark.asyncio
async def test_worker_missing_target_column_transitions_to_failed(db: DatabaseManager):
    """Verify that if dataset is missing the specified target column, experiment transitions to FAILED."""
    tenant_id = generate_uuid7()
    project_id = generate_uuid7()
    dataset_id = generate_uuid7()
    dsv_id = generate_uuid7()
    exp_id = generate_uuid7()

    storage_dict: dict[str, bytes] = {}
    mock_storage = MagicMock()
    mock_storage.get_dataset_key.return_value = (
        f"tenants/{tenant_id}/datasets/{dataset_id}/1.0/data.parquet"
    )
    mock_storage.get_object.side_effect = lambda k: storage_dict[k]

    # Parquet lacking "target" column
    df = pd.DataFrame({"f1": [1.0, 2.0, 3.0], "f2": [4.0, 5.0, 6.0]})
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    storage_dict[mock_storage.get_dataset_key.return_value] = buf.getvalue()

    async with db.session() as sess:
        t = TenantOrm(id=tenant_id, name="Tenant Neg 2")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Project Neg 2")
        sess.add_all([t, p])

        model_svc = ModelService(sess)
        await model_svc.seed_catalog()
        m_repo = ModelRepository(sess)
        mv = await m_repo.get_version("random_forest", "1.0.0")
        assert mv is not None

        ds = DatasetOrm(
            id=dataset_id, tenant_id=tenant_id, project_id=project_id, name="DS", format="parquet"
        )
        dsv = DatasetVersionOrm(
            id=dsv_id,
            dataset_id=dataset_id,
            version="1.0",
            schema_json={"columns": []},
            row_count=3,
            column_count=2,
            size_bytes=len(buf.getvalue()),
            content_hash="sha256:dummy",
            storage_uri="s3://bucket/key",
        )
        sess.add_all([ds, dsv])

        spec = ExperimentSpec(
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv.id,
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="nonexistent_target",
            evaluation_config=EvaluationConfig(primary_metric="accuracy"),
            created_by="test-user",
        )
        exp = ExperimentOrm(
            id=exp_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv.id,
            spec_json=spec.model_dump(),
            status="QUEUED",
            created_by="test-user",
        )
        sess.add(exp)

    async with db.session() as sess:
        runner = WorkerRunner(session=sess, storage_service=mock_storage)
        with pytest.raises((ValueError, KeyError)):
            await runner.execute_experiment(exp_id, tenant_id)

    # Verify experiment transitioned to FAILED
    async with db.session() as sess:
        e_repo = ExperimentRepository(sess)
        saved_exp = await e_repo.get_experiment(tenant_id, exp_id)
        assert saved_exp is not None
        assert saved_exp.status == "FAILED"
        assert len(saved_exp.runs) == 1
        assert saved_exp.runs[0].status == "FAILED"


@pytest.mark.asyncio
async def test_worker_timeout_transitions_to_failed(db: DatabaseManager):
    """Verify that training exceeding runtime timeout marks experiment FAILED."""
    tenant_id = generate_uuid7()
    project_id = generate_uuid7()
    dataset_id = generate_uuid7()
    dsv_id = generate_uuid7()
    exp_id = generate_uuid7()

    storage_dict: dict[str, bytes] = {}
    mock_storage = MagicMock()
    mock_storage.get_dataset_key.return_value = (
        f"tenants/{tenant_id}/datasets/{dataset_id}/1.0/data.parquet"
    )

    def slow_get_object(k):
        return storage_dict[k]

    mock_storage.get_object.side_effect = slow_get_object

    df = pd.DataFrame({"f1": [1.0, 2.0], "target": [0, 1]})
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    storage_dict[mock_storage.get_dataset_key.return_value] = buf.getvalue()

    async with db.session() as sess:
        t = TenantOrm(id=tenant_id, name="Tenant Timeout")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Project Timeout")
        sess.add_all([t, p])

        model_svc = ModelService(sess)
        await model_svc.seed_catalog()
        m_repo = ModelRepository(sess)
        mv = await m_repo.get_version("random_forest", "1.0.0")
        assert mv is not None

        ds = DatasetOrm(
            id=dataset_id, tenant_id=tenant_id, project_id=project_id, name="DS", format="parquet"
        )
        dsv = DatasetVersionOrm(
            id=dsv_id,
            dataset_id=dataset_id,
            version="1.0",
            schema_json={"columns": []},
            row_count=2,
            column_count=2,
            size_bytes=len(buf.getvalue()),
            content_hash="sha256:dummy",
            storage_uri="s3://bucket/key",
        )
        sess.add_all([ds, dsv])

        spec = ExperimentSpec(
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv.id,
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="target",
            evaluation_config=EvaluationConfig(primary_metric="accuracy"),
            resource_policy=ResourcePolicy(max_runtime_seconds=10),
            created_by="test-user",
        )
        spec_dict = spec.model_dump()
        spec_dict["resource_policy"]["max_runtime_seconds"] = 10

        exp = ExperimentOrm(
            id=exp_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv.id,
            spec_json=spec_dict,
            status="QUEUED",
            created_by="test-user",
        )
        sess.add(exp)

    # Mock _execute_training_job to simulate a timeout
    async with db.session() as sess:
        runner = WorkerRunner(session=sess, storage_service=mock_storage)

        async def simulated_timeout(*args, **kwargs):
            await asyncio.sleep(2)

        runner._execute_training_job = simulated_timeout

        with patch.object(WorkerSandbox, "__init__", return_value=None):
            sandbox_instance = WorkerSandbox()
            sandbox_instance.timeout_seconds = 0.05
            sandbox_instance.max_memory_mb = 4096
            with patch("ml_mcp.workers.runner.WorkerSandbox", return_value=sandbox_instance):
                with pytest.raises(ResourceLimitExceededError) as exc:
                    await runner.execute_experiment(exp_id, tenant_id)
                assert "timeout" in str(exc.value).lower() or "limit" in str(exc.value).lower()

    # Verify status is FAILED
    async with db.session() as sess:
        e_repo = ExperimentRepository(sess)
        saved_exp = await e_repo.get_experiment(tenant_id, exp_id)
        assert saved_exp.status == "FAILED"
        assert saved_exp.runs[0].status == "FAILED"
