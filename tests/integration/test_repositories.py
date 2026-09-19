"""Integration tests verifying full functionality of all repositories."""

import pytest
from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.session import DatabaseManager
from ml_mcp.infrastructure.postgres.models import (
    TenantOrm,
    ProjectOrm,
    ModelOrm,
    ModelVersionOrm,
    DatasetOrm,
    DatasetVersionOrm,
    ExperimentOrm,
    ExperimentRunOrm,
    MetricOrm,
    ArtifactOrm,
    OutboxEventOrm,
    AuditEventOrm,
)
from ml_mcp.infrastructure.postgres.repositories import (
    ModelRepository,
    DatasetRepository,
    ExperimentRepository,
    MetricRepository,
    ArtifactRepository,
    OutboxRepository,
    AuditRepository,
)


@pytest.fixture
async def db():
    db_mgr = DatabaseManager()
    db_mgr.initialize(custom_url="sqlite+aiosqlite:///file:repodb?mode=memory&cache=shared&uri=true")
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_mgr
    await db_mgr.close()


@pytest.mark.asyncio
async def test_full_repository_suite(db: DatabaseManager):
    tenant_id = generate_uuid7()
    project_id = generate_uuid7()

    # 1. Setup Tenant and Project
    async with db.session() as sess:
        t = TenantOrm(id=tenant_id, name="Test Tenant")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Test Project")
        sess.add_all([t, p])

    # 2. ModelRepository
    async with db.session() as sess:
        repo = ModelRepository(sess)
        model = ModelOrm(
            id="rf-classifier",
            name="Random Forest Classifier",
            family="random_forest",
            publisher="ModelLab",
        )
        await repo.create_model(model)
        version = ModelVersionOrm(
            model_id="rf-classifier",
            version="1.0.0",
            container_image_digest="sha256:1111",
            supported_task_types=["binary_classification"],
            hyperparameters_schema=[{"name": "n_estimators", "type": "int", "default": 100}],
        )
        await repo.create_version(version)

    async with db.session() as sess:
        repo = ModelRepository(sess)
        fetched_model = await repo.get_by_id("rf-classifier")
        assert fetched_model is not None
        assert fetched_model.name == "Random Forest Classifier"
        assert len(fetched_model.versions) == 1
        assert fetched_model.versions[0].version == "1.0.0"

    # 3. DatasetRepository
    ds_id = generate_uuid7()
    dsv_id = generate_uuid7()
    async with db.session() as sess:
        repo = DatasetRepository(sess)
        dataset = DatasetOrm(
            id=ds_id,
            tenant_id=tenant_id,
            project_id=project_id,
            name="Churn Data",
            format="parquet",
        )
        await repo.create_dataset(dataset)
        version = DatasetVersionOrm(
            id=dsv_id,
            dataset_id=ds_id,
            version="1.0",
            schema_json={"columns": [{"name": "target", "type": "int"}]},
            row_count=1000,
            column_count=5,
            size_bytes=4096,
            content_hash="sha256:2222",
            storage_uri="s3://modellab-artifacts/datasets/1.parquet",
        )
        await repo.create_version(version)

    async with db.session() as sess:
        repo = DatasetRepository(sess)
        fetched_ds = await repo.get_dataset(tenant_id, ds_id)
        assert fetched_ds is not None
        assert fetched_ds.name == "Churn Data"
        assert len(fetched_ds.versions) == 1
        # Cross-tenant isolation check
        assert await repo.get_dataset("wrong-tenant", ds_id) is None

    # 4. ExperimentRepository & Outbox
    exp_id = generate_uuid7()
    outbox_id = generate_uuid7()
    async with db.session() as sess:
        repo = ExperimentRepository(sess)
        experiment = ExperimentOrm(
            id=exp_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=fetched_model.versions[0].id,
            spec_json={"task_type": "binary_classification"},
            status="QUEUED",
            idempotency_key="idemp-key-101",
            created_by="user-test",
        )
        outbox = OutboxEventOrm(
            id=outbox_id,
            event_type="EXPERIMENT_SUBMITTED",
            aggregate_type="EXPERIMENT",
            aggregate_id=exp_id,
            payload_json={"experiment_id": exp_id},
        )
        await repo.create_experiment(experiment, initial_outbox_event=outbox)

    async with db.session() as sess:
        repo = ExperimentRepository(sess)
        idemp_exp = await repo.get_by_idempotency_key(tenant_id, project_id, "idemp-key-101")
        assert idemp_exp is not None
        assert idemp_exp.id == exp_id

        # Update status
        updated = await repo.update_status(tenant_id, exp_id, "RUNNING")
        assert updated is True

        # Create and update Run
        run = ExperimentRunOrm(experiment_id=exp_id, run_number=1, status="RUNNING")
        await repo.create_run(run)
        run_id = run.id

    async with db.session() as sess:
        repo = ExperimentRepository(sess)
        updated_run = await repo.update_run(run_id, "SUCCEEDED", duration_seconds=12.5, end_time=True)
        assert updated_run is True
        latest_run = await repo.get_latest_run(exp_id)
        assert latest_run is not None
        assert latest_run.status == "SUCCEEDED"
        assert latest_run.duration_seconds == 12.5

    # 5. MetricRepository
    async with db.session() as sess:
        repo = MetricRepository(sess)
        metrics = [
            MetricOrm(experiment_id=exp_id, run_id=run_id, metric_name="roc_auc", metric_value=0.92, split="validation"),
            MetricOrm(experiment_id=exp_id, run_id=run_id, metric_name="f1", metric_value=0.85, split="validation"),
        ]
        await repo.record_metrics(metrics)

    async with db.session() as sess:
        repo = MetricRepository(sess)
        recorded = await repo.get_metrics(tenant_id, exp_id)
        assert len(recorded) == 2
        comp = await repo.compare_metrics(tenant_id, [exp_id])
        assert comp[exp_id]["roc_auc"] == 0.92

    # 6. ArtifactRepository
    art_id = generate_uuid7()
    async with db.session() as sess:
        repo = ArtifactRepository(sess)
        art = ArtifactOrm(
            id=art_id,
            tenant_id=tenant_id,
            experiment_id=exp_id,
            artifact_type="model",
            storage_uri="s3://bucket/model.joblib",
            size_bytes=1024,
            content_hash="sha256:3333",
        )
        await repo.record_artifact(art)

    async with db.session() as sess:
        repo = ArtifactRepository(sess)
        art_fetched = await repo.get_artifact(tenant_id, art_id)
        assert art_fetched is not None
        assert art_fetched.artifact_type == "model"

    # 7. OutboxRepository
    async with db.session() as sess:
        outbox_repo = OutboxRepository(sess)
        pending = await outbox_repo.fetch_pending()
        assert len(pending) == 1
        assert pending[0].id == outbox_id
        delivered = await outbox_repo.mark_delivered(outbox_id)
        assert delivered is True

    # 8. AuditRepository
    async with db.session() as sess:
        audit_repo = AuditRepository(sess)
        audit_event = AuditEventOrm(
            principal_id="user-1",
            tenant_id=tenant_id,
            project_id=project_id,
            action="EXPERIMENT_CREATE",
            resource_type="experiment",
            resource_id=exp_id,
            result="SUCCESS",
        )
        await audit_repo.record_event(audit_event)

    async with db.session() as sess:
        audit_repo = AuditRepository(sess)
        logs = await audit_repo.list_events(tenant_id)
        assert len(logs) == 1
        assert logs[0].action == "EXPERIMENT_CREATE"
