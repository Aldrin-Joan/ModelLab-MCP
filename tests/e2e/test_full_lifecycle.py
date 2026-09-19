"""End-to-End Test for ModelLab ML Experimentation Lifecycle.

Validates the full journey across all 5 tool categories:
1. Discovery: list_models, get_model
2. Datasets: validate_dataset, register_dataset, inspect_dataset
3. Experimentation: create_experiment, get_experiment
4. Worker Execution: sandboxed training, metric evaluation, artifact persistence
5. Results & Artifacts: get_experiment_metrics, get_experiment_predictions, list_experiment_artifacts, read_experiment_artifact, compare_experiments
6. Diagnostics: analyze_experiment, analyze_model_errors, check_experiment_validity
"""

import base64
import json
import pytest
from ml_mcp.application.models.service import ModelService
from ml_mcp.domain.policies import Principal, Role
from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.models import ProjectOrm, TenantOrm
from ml_mcp.infrastructure.postgres.session import DatabaseManager, get_db_manager
from ml_mcp.server.app import create_server
from ml_mcp.server.context import set_current_principal
from ml_mcp.workers.runner import WorkerRunner


def extract_result(tool_res):
    """Unwrap structured content or JSON text from FastMCP tool result."""
    if tool_res.structured_content is not None:
        if isinstance(tool_res.structured_content, dict) and "result" in tool_res.structured_content and len(tool_res.structured_content) == 1:
            return tool_res.structured_content["result"]
        return tool_res.structured_content
    return json.loads(tool_res.content[0].text)


@pytest.fixture
async def e2e_env():
    db_mgr = get_db_manager()
    db_mgr.initialize(custom_url="sqlite+aiosqlite:///file:e2e_db?mode=memory&cache=shared&uri=true")
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed model catalog
    async with db_mgr.session() as sess:
        service = ModelService(sess)
        await service.seed_catalog()

    tenant_id = "tenant-e2e"
    project_id = "project-e2e"

    async with db_mgr.session() as sess:
        t = TenantOrm(id=tenant_id, name="E2E Tenant")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="E2E Project")
        sess.add_all([t, p])

    principal = Principal(
        principal_id="researcher-e2e",
        tenant_id=tenant_id,
        project_ids=[project_id],
        role=Role.ADMIN,
        scopes={"*"},
    )
    set_current_principal(principal)

    yield {
        "db_mgr": db_mgr,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "principal": principal,
    }

    set_current_principal(None)
    await db_mgr.close()


@pytest.mark.asyncio
async def test_full_ml_experiment_lifecycle_e2e(e2e_env: dict):
    """Execute complete end-to-end journey from dataset ingestion to diagnostic verification."""
    server = create_server()
    db_mgr = e2e_env["db_mgr"]
    tenant_id = e2e_env["tenant_id"]
    project_id = e2e_env["project_id"]

    # -------------------------------------------------------------------------
    # Step 1: Discovery
    # -------------------------------------------------------------------------
    models_res = await server.call_tool("list_models", {})
    assert not models_res.is_error
    models = extract_result(models_res)
    assert len(models) == 7

    rf_details_res = await server.call_tool("get_model", {"model_id": "random_forest"})
    rf_details = extract_result(rf_details_res)
    assert rf_details["model_id"] == "random_forest"
    rf_version_id = rf_details["versions"][0]["version_id"]

    lr_details_res = await server.call_tool("get_model", {"model_id": "logistic_regression"})
    lr_version_id = extract_result(lr_details_res)["versions"][0]["version_id"]

    # -------------------------------------------------------------------------
    # Step 2: Dataset Registration & Inspection
    # -------------------------------------------------------------------------
    # Build 60-row clean tabular dataset with 3 features and binary target
    csv_rows = ["num1,num2,cat1,target"]
    for i in range(60):
        c = "A" if i % 2 == 0 else "B"
        t = 1 if i % 3 == 0 else 0
        csv_rows.append(f"{float(i)},{float(i * 2)},{c},{t}")
    csv_content = "\n".join(csv_rows) + "\n"
    csv_b64 = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")

    # Validate first
    val_res = await server.call_tool("validate_dataset", {"format": "csv", "data_base64": csv_b64})
    assert not val_res.is_error
    assert extract_result(val_res)["row_count"] == 60

    # Register dataset
    reg_res = await server.call_tool(
        "register_dataset",
        {
            "project_id": project_id,
            "name": "e2e_tabular_data",
            "description": "Synthetic dataset for end-to-end test",
            "format": "csv",
            "data_base64": csv_b64,
            "version": "1.0",
        },
    )
    assert not reg_res.is_error
    reg_payload = extract_result(reg_res)
    dataset_id = reg_payload["dataset_id"]
    dataset_version_id = reg_payload["version_id"]

    # Inspect dataset
    insp_res = await server.call_tool(
        "inspect_dataset",
        {"dataset_id": dataset_id, "version": "1.0", "sample_rows": 5},
    )
    assert not insp_res.is_error
    insp_payload = extract_result(insp_res)
    assert insp_payload["row_count"] == 60
    assert len(insp_payload["sample_rows"]) == 5

    # -------------------------------------------------------------------------
    # Step 3: Experiment Creation (Random Forest)
    # -------------------------------------------------------------------------
    exp1_res = await server.call_tool(
        "create_experiment",
        {
            "project_id": project_id,
            "dataset_version_id": dataset_version_id,
            "model_version_id": rf_version_id,
            "task_type": "binary_classification",
            "target_column": "target",
            "feature_columns": ["num1", "num2", "cat1"],
            "primary_metric": "roc_auc",
            "additional_metrics": ["accuracy", "f1", "precision", "recall"],
            "hyperparameters": {"n_estimators": 10, "max_depth": 5},
            "random_seed": 42,
        },
    )
    assert not exp1_res.is_error
    exp1_id = extract_result(exp1_res)["experiment_id"]

    # Verify status is QUEUED
    get_exp_res = await server.call_tool("get_experiment", {"experiment_id": exp1_id})
    assert extract_result(get_exp_res)["status"] == "QUEUED"

    # -------------------------------------------------------------------------
    # Step 4: Worker Runner Execution
    # -------------------------------------------------------------------------
    async with db_mgr.session() as sess:
        runner = WorkerRunner(sess)
        await runner.execute_experiment(exp1_id, tenant_id)

    # Verify experiment transitioned to SUCCEEDED
    get_exp_done = await server.call_tool("get_experiment", {"experiment_id": exp1_id})
    exp_details = extract_result(get_exp_done)
    assert exp_details["status"] == "SUCCEEDED"
    assert exp_details["runs_count"] >= 1
    assert exp_details["metrics_count"] > 0
    assert exp_details["artifacts_count"] > 0
    assert exp_details["created_at"] is not None

    # -------------------------------------------------------------------------
    # Step 5: Results & Artifacts Inspection
    # -------------------------------------------------------------------------
    # 1. Metrics
    metrics_res = await server.call_tool("get_experiment_metrics", {"experiment_id": exp1_id})
    assert not metrics_res.is_error
    metrics = extract_result(metrics_res)
    assert "val_roc_auc" in metrics or "train_roc_auc" in metrics or len(metrics) > 0

    # 2. Predictions
    preds_res = await server.call_tool("get_experiment_predictions", {"experiment_id": exp1_id, "limit": 10})
    assert not preds_res.is_error
    pred_data = extract_result(preds_res)
    assert "sample_preview" in pred_data
    predictions = pred_data["sample_preview"]
    assert len(predictions) > 0
    first_pred = predictions[0]
    assert "y_true" in first_pred
    assert "y_pred" in first_pred

    # 3. Artifacts
    art_res = await server.call_tool("list_experiment_artifacts", {"experiment_id": exp1_id})
    assert not art_res.is_error
    artifacts = extract_result(art_res)
    assert len(artifacts) >= 2
    artifact_types = {a["artifact_type"] for a in artifacts}
    assert "model" in artifact_types

    # Read specific artifact
    model_art = next(a for a in artifacts if a["artifact_type"] == "model")
    read_art_res = await server.call_tool("read_experiment_artifact", {"artifact_id": model_art["artifact_id"]})
    assert not read_art_res.is_error
    art_data = extract_result(read_art_res)
    assert art_data["download_url"] is not None

    # -------------------------------------------------------------------------
    # Step 6: Diagnostic & Quality Analysis Tools
    # -------------------------------------------------------------------------
    # 1. Automated Experiment Diagnostics
    diag_res = await server.call_tool("analyze_experiment", {"experiment_id": exp1_id})
    assert not diag_res.is_error
    diag_report = extract_result(diag_res)
    assert "overfitting_signals" in diag_report
    assert "leakage_signals" in diag_report
    assert "summary" in diag_report

    # 2. Error Analysis
    err_res = await server.call_tool("analyze_model_errors", {"experiment_id": exp1_id})
    assert not err_res.is_error
    err_report = extract_result(err_res)
    assert "error_patterns" in err_report
    assert "overfitting_diagnosis" in err_report

    # 3. Validity & Reproducibility Check
    valid_res = await server.call_tool("check_experiment_validity", {"experiment_id": exp1_id})
    assert not valid_res.is_error
    valid_payload = extract_result(valid_res)
    assert "is_valid" in valid_payload
    assert "overfitting_severity" in valid_payload

    # -------------------------------------------------------------------------
    # Step 7: Create 2nd Experiment & Compare Experiments
    # -------------------------------------------------------------------------
    exp2_res = await server.call_tool(
        "create_experiment",
        {
            "project_id": project_id,
            "dataset_version_id": dataset_version_id,
            "model_version_id": lr_version_id,
            "task_type": "binary_classification",
            "target_column": "target",
            "primary_metric": "roc_auc",
            "hyperparameters": {"C": 0.5},
            "random_seed": 42,
        },
    )
    exp2_id = extract_result(exp2_res)["experiment_id"]
    async with db_mgr.session() as sess:
        runner2 = WorkerRunner(sess)
        await runner2.execute_experiment(exp2_id, tenant_id)

    cmp_res = await server.call_tool("compare_experiments", {"experiment_ids": [exp1_id, exp2_id]})
    assert not cmp_res.is_error
    cmp_payload = extract_result(cmp_res)
    assert len(cmp_payload["compared_experiment_ids"]) == 2
    assert len(cmp_payload["validation_metrics_by_experiment"]) == 2
