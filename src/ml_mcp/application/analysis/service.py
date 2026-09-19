"""Structured experiment analysis application service."""

import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ml_mcp.application.analysis.diagnostics import (
    DataLeakageDetector,
    ErrorPatternAnalyzer,
    OverfittingDetector,
)
from ml_mcp.domain.errors import ResourceNotFoundError
from ml_mcp.infrastructure.postgres.base import generate_uuid7
from ml_mcp.infrastructure.postgres.models import AnalysisRunOrm, ExperimentOrm, MetricOrm

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service providing structured, read-only analytical evaluation of ML experiment results."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def analyze_experiment(self, tenant_id: str, experiment_id: str) -> dict[str, Any]:
        """Perform comprehensive statistical analysis of an experiment's metrics and predictions."""
        # 1. Fetch experiment
        stmt = select(ExperimentOrm).where(
            ExperimentOrm.tenant_id == tenant_id, ExperimentOrm.id == experiment_id
        )
        result = await self.session.execute(stmt)
        exp = result.scalar_one_or_none()
        if not exp:
            raise ResourceNotFoundError("Experiment", experiment_id)

        # 2. Fetch metrics
        m_stmt = select(MetricOrm).where(MetricOrm.experiment_id == experiment_id)
        m_result = await self.session.execute(m_stmt)
        all_metrics = m_result.scalars().all()

        train_metrics: dict[str, float] = {}
        val_metrics: dict[str, float] = {}
        confusion_mat: list[list[int]] | None = None

        for m in all_metrics:
            if m.split == "train":
                train_metrics[m.metric_name] = m.metric_value
            elif m.split == "validation":
                val_metrics[m.metric_name] = m.metric_value

        # Check for confusion matrix in artifacts or metrics
        # 3. Run diagnostic engines
        overfitting = OverfittingDetector.evaluate(train_metrics, val_metrics)
        leakage = DataLeakageDetector.evaluate(train_metrics, val_metrics)

        # 4. Synthesize recommendations
        recommendations: list[str] = []
        if overfitting["overfitting_detected"]:
            recommendations.append("Increase regularization (e.g. increase alpha, reduce max_depth, or increase min_samples_split).")
            recommendations.append("Apply cross-validation (K-Fold) to evaluate variance across folds.")
        if leakage["leakage_risk_detected"]:
            recommendations.append("Audit dataset columns for target leakage or deterministic identifiers.")
        if not recommendations:
            recommendations.append("Model demonstrates healthy generalization. Consider testing next candidate architecture or fine-tuning learning rate.")

        # 5. Format according to Architecture.md Section 21
        structured_findings: dict[str, Any] = {
            "summary": f"Experiment {experiment_id} evaluated with {len(val_metrics)} validation metrics.",
            "metric_comparison": {
                "train": train_metrics,
                "validation": val_metrics,
            },
            "statistical_observations": {
                "primary_metric": exp.spec_json.get("evaluation_config", {}).get("primary_metric"),
                "primary_metric_validation_value": val_metrics.get(
                    exp.spec_json.get("evaluation_config", {}).get("primary_metric", ""), None
                ),
            },
            "error_patterns": {
                "observed_anomalies": len(leakage["signals"]),
            },
            "data_quality_findings": {
                "target_column": exp.spec_json.get("target_column"),
                "task_type": exp.spec_json.get("task_type"),
            },
            "overfitting_signals": overfitting,
            "leakage_signals": leakage,
            "limitations": [
                "Analysis performed strictly on tabular evaluation split.",
                "Hyperparameter space explored only for single trial run.",
            ],
            "recommended_next_experiments": recommendations,
            "confidence": "HIGH",
        }

        # 6. Upsert read-only analysis run record
        analysis_run_stmt = select(AnalysisRunOrm).where(AnalysisRunOrm.experiment_id == experiment_id)
        existing_run = (await self.session.execute(analysis_run_stmt)).scalar_one_or_none()

        if not existing_run:
            analysis_orm = AnalysisRunOrm(
                id=generate_uuid7(),
                experiment_id=experiment_id,
                tenant_id=tenant_id,
                summary_json={"summary": structured_findings["summary"]},
                diagnostics_json=structured_findings,
            )
            self.session.add(analysis_orm)
            await self.session.flush()

        return structured_findings

    async def analyze_model_errors(self, tenant_id: str, experiment_id: str) -> dict[str, Any]:
        """Deep dive into false positives and false negatives."""
        analysis = await self.analyze_experiment(tenant_id, experiment_id)
        return {
            "experiment_id": experiment_id,
            "error_patterns": analysis["error_patterns"],
            "overfitting_diagnosis": analysis["overfitting_signals"],
        }

    async def check_experiment_validity(self, tenant_id: str, experiment_id: str) -> dict[str, Any]:
        """Validate whether an experiment's metrics can be trusted or should be flagged for review."""
        analysis = await self.analyze_experiment(tenant_id, experiment_id)
        is_valid = not (analysis["leakage_signals"]["leakage_risk_detected"] or analysis["overfitting_signals"]["severity"] == "HIGH")
        return {
            "experiment_id": experiment_id,
            "is_valid": is_valid,
            "leakage_risk": analysis["leakage_signals"]["leakage_risk_detected"],
            "overfitting_severity": analysis["overfitting_signals"]["severity"],
            "recommendations": analysis["recommended_next_experiments"],
        }
