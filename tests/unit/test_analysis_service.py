"""Unit tests for AnalysisService and diagnostic evaluators."""

import pytest

from ml_mcp.application.analysis.diagnostics import (
    DataLeakageDetector,
    ErrorPatternAnalyzer,
    OverfittingDetector,
)
from ml_mcp.application.analysis.service import AnalysisService
from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.models import (
    DatasetOrm,
    DatasetVersionOrm,
    ExperimentOrm,
    MetricOrm,
    ModelOrm,
    ModelVersionOrm,
    ProjectOrm,
    TenantOrm,
)
from ml_mcp.infrastructure.postgres.session import DatabaseManager


def test_overfitting_detector():
    train_m = {"accuracy": 0.98, "roc_auc": 0.99}
    val_m = {"accuracy": 0.75, "roc_auc": 0.78}

    res = OverfittingDetector.evaluate(train_m, val_m, threshold=0.15)
    assert res["overfitting_detected"] is True
    assert res["severity"] == "LOW" or res["severity"] == "MEDIUM" or res["severity"] == "HIGH"
    assert "memorization" in res["observation"]


def test_data_leakage_detector():
    # Suspicious perfect metric
    train_m = {"accuracy": 0.85}
    val_m = {"accuracy": 1.0}

    res = DataLeakageDetector.evaluate(train_m, val_m)
    assert res["leakage_risk_detected"] is True
    assert len(res["signals"]) > 0


def test_confusion_matrix_analyzer():
    # 2x2 matrix: [[TN, FP], [FN, TP]]
    cm = [[80, 20], [10, 90]]
    res = ErrorPatternAnalyzer.evaluate_confusion_matrix(cm)
    assert res["total_samples"] == 200
    assert res["true_positives"] == 90
    assert res["true_negatives"] == 80
    assert res["false_positives"] == 20
    assert res["false_negatives"] == 10
    assert res["dominant_error_pattern"] == "FALSE_POSITIVES"


@pytest.mark.asyncio
async def test_analysis_service_execution():
    db_mgr = DatabaseManager()
    db_mgr.initialize(
        custom_url="sqlite+aiosqlite:///file:analysisdb?mode=memory&cache=shared&uri=true"
    )
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tenant_id = generate_uuid7()
    project_id = generate_uuid7()
    exp_id = generate_uuid7()
    mv_id = generate_uuid7()
    dsv_id = generate_uuid7()

    async with db_mgr.session() as sess:
        t = TenantOrm(id=tenant_id, name="Analysis Tenant")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Analysis Project")
        m = ModelOrm(id="rf", name="RF", family="random_forest")
        mv = ModelVersionOrm(
            id=mv_id,
            model_id="rf",
            version="1.0",
            container_image_digest="sha256:1",
            supported_task_types=["binary_classification"],
        )
        ds = DatasetOrm(
            id="ds", tenant_id=tenant_id, project_id=project_id, name="DS", format="parquet"
        )
        dsv = DatasetVersionOrm(
            id=dsv_id,
            dataset_id="ds",
            version="1.0",
            schema_json={},
            row_count=100,
            column_count=2,
            size_bytes=10,
            content_hash="h",
            storage_uri="s3://",
        )

        exp = ExperimentOrm(
            id=exp_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_version_id=dsv_id,
            model_version_id=mv_id,
            spec_json={
                "task_type": "binary_classification",
                "target_column": "target",
                "evaluation_config": {"primary_metric": "roc_auc"},
            },
            status="SUCCEEDED",
            created_by="user-analysis",
        )
        m1 = MetricOrm(
            experiment_id=exp_id,
            run_id="run-1",
            metric_name="roc_auc",
            metric_value=0.95,
            split="train",
        )
        m2 = MetricOrm(
            experiment_id=exp_id,
            run_id="run-1",
            metric_name="roc_auc",
            metric_value=0.92,
            split="validation",
        )

        sess.add_all([t, p, m, mv, ds, dsv, exp, m1, m2])

    async with db_mgr.session() as sess:
        service = AnalysisService(sess)
        analysis = await service.analyze_experiment(tenant_id, exp_id)

        assert "summary" in analysis
        assert "metric_comparison" in analysis
        assert analysis["metric_comparison"]["validation"]["roc_auc"] == 0.92
        assert "overfitting_signals" in analysis
        assert "recommended_next_experiments" in analysis

        # Verify analysis run was recorded in DB
        from sqlalchemy import select

        from ml_mcp.infrastructure.postgres.models import AnalysisRunOrm

        stmt = select(AnalysisRunOrm).where(AnalysisRunOrm.experiment_id == exp_id)
        run_record = (await sess.execute(stmt)).scalar_one_or_none()
        assert run_record is not None
        assert run_record.tenant_id == tenant_id

    await db_mgr.close()
