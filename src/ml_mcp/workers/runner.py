"""Worker runner executing end-to-end ML model training and artifact persistence."""

import asyncio
import io
import logging
import time
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from ml_mcp.domain.value_objects import ExperimentSpec
from ml_mcp.infrastructure.object_storage.s3 import S3StorageService, get_storage_service
from ml_mcp.infrastructure.postgres.base import generate_uuid7
from ml_mcp.infrastructure.postgres.models import (
    ArtifactOrm,
    ExperimentRunOrm,
    MetricOrm,
)
from ml_mcp.infrastructure.postgres.repositories import (
    ArtifactRepository,
    DatasetRepository,
    ExperimentRepository,
    MetricRepository,
    ModelRepository,
)
from ml_mcp.workers.preprocessing import PreprocessingPipeline
from ml_mcp.workers.sandbox import WorkerSandbox
from ml_mcp.workers.trainers import get_trainer

logger = logging.getLogger(__name__)


class WorkerRunner:
    """Orchestrates ML experiment execution, metric logging, and artifact persistence."""

    def __init__(
        self,
        session: AsyncSession,
        storage_service: S3StorageService | None = None,
    ) -> None:
        self.session = session
        self.storage = storage_service or get_storage_service()
        self.exp_repo = ExperimentRepository(session)
        self.ds_repo = DatasetRepository(session)
        self.model_repo = ModelRepository(session)
        self.metric_repo = MetricRepository(session)
        self.artifact_repo = ArtifactRepository(session)

    async def execute_experiment(
        self,
        experiment_id: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Execute experiment end-to-end within isolated sandbox."""
        start_time = time.time()

        # 1. Fetch experiment record
        exp = await self.exp_repo.get_experiment(tenant_id, experiment_id)
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found for tenant '{tenant_id}'")

        spec = ExperimentSpec(**exp.spec_json)

        # 2. Mark running & create run record
        await self.exp_repo.update_status(tenant_id, experiment_id, "RUNNING")
        run_id = generate_uuid7()
        run_orm = ExperimentRunOrm(
            id=run_id,
            experiment_id=experiment_id,
            run_number=len(exp.runs) + 1,
            status="RUNNING",
            worker_id="worker-cpu-01",
        )
        await self.exp_repo.create_run(run_orm)

        sandbox = WorkerSandbox(
            timeout_seconds=spec.resource_policy.max_runtime_seconds,
            max_memory_mb=spec.resource_policy.max_memory_mb,
        )

        try:
            result = await sandbox.execute(self._execute_training_job, exp, spec, run_id)
            duration = time.time() - start_time
            await self.exp_repo.update_run(
                run_id, "SUCCEEDED", duration_seconds=duration, end_time=True
            )
            await self.exp_repo.update_status(tenant_id, experiment_id, "SUCCEEDED")
            return result

        except Exception as exc:
            duration = time.time() - start_time
            logger.error("Experiment %s execution failed: %s", experiment_id, exc)
            await self.exp_repo.update_run(
                run_id, "FAILED", duration_seconds=duration, failure_reason=str(exc), end_time=True
            )
            await self.exp_repo.update_status(tenant_id, experiment_id, "FAILED")
            raise

    async def _execute_training_job(
        self,
        exp: Any,
        spec: ExperimentSpec,
        run_id: str,
    ) -> dict[str, Any]:
        tenant_id = exp.tenant_id
        experiment_id = exp.id

        # 1. Download dataset Parquet from S3
        dsv = await self.ds_repo.get_version_by_id(tenant_id, spec.dataset_version_id)
        if not dsv:
            raise ValueError(f"DatasetVersion '{spec.dataset_version_id}' not found")

        dataset_key = self.storage.get_dataset_key(
            tenant_id, dsv.dataset_id, dsv.version, "data.parquet"
        )
        dataset_bytes = await asyncio.to_thread(self.storage.get_object, dataset_key)
        df = await asyncio.to_thread(pd.read_parquet, io.BytesIO(dataset_bytes))

        # 2. Preprocess features and create leak-free splits
        prep = PreprocessingPipeline(
            target_column=spec.target_column,
            task_type=spec.task_type,
            feature_columns=spec.feature_columns,
            split_strategy=spec.split_strategy,
        )
        folds = await asyncio.to_thread(prep.fit_transform_folds, df)
        X_tr, X_val, y_tr, y_val, fitted_transformer = folds[0]

        # 3. Fetch model metadata and instantiate trainer
        model_version = exp.model_version
        model_family = model_version.model.family
        trainer = get_trainer(model_family)

        # 4. Train model
        train_result = await asyncio.to_thread(
            trainer.train,
            X_tr=X_tr,
            y_tr=y_tr,
            X_val=X_val,
            y_val=y_val,
            task_type=spec.task_type,
            hyperparameters=spec.hyperparameters,
            random_seed=spec.random_seed,
            max_cpu_cores=spec.resource_policy.max_cpu_cores,
        )

        # 5. Save model artifact to S3
        model_key = self.storage.get_experiment_artifact_key(
            tenant_id, experiment_id, "model", "model.joblib"
        )
        model_bytes = await asyncio.to_thread(train_result.serialize_artifact)
        model_uri, model_hash = await asyncio.to_thread(
            self.storage.put_object,
            key=model_key,
            data=model_bytes,
            content_type="application/octet-stream",
        )
        await self.artifact_repo.record_artifact(
            ArtifactOrm(
                id=generate_uuid7(),
                tenant_id=tenant_id,
                experiment_id=experiment_id,
                artifact_type="model",
                storage_uri=model_uri,
                size_bytes=len(train_result.model_artifact_bytes),
                content_hash=model_hash,
                metadata_json={"model_family": model_family, "task_type": spec.task_type.value},
            )
        )

        # 6. Save predictions to S3
        pred_df = pd.DataFrame(
            {
                "y_true": y_val,
                "y_pred": train_result.val_predictions,
            }
        )
        if train_result.val_probabilities is not None:
            if train_result.val_probabilities.ndim == 1:
                pred_df["y_proba"] = train_result.val_probabilities
            else:
                for idx in range(train_result.val_probabilities.shape[1]):
                    pred_df[f"y_proba_class_{idx}"] = train_result.val_probabilities[:, idx]

        pred_buf = io.BytesIO()
        await asyncio.to_thread(pred_df.to_parquet, pred_buf, index=False)
        pred_bytes = pred_buf.getvalue()

        pred_key = self.storage.get_experiment_artifact_key(
            tenant_id, experiment_id, "predictions", "predictions.parquet"
        )
        pred_uri, pred_hash = await asyncio.to_thread(
            self.storage.put_object,
            key=pred_key,
            data=pred_bytes,
            content_type="application/vnd.apache.parquet",
        )
        await self.artifact_repo.record_artifact(
            ArtifactOrm(
                id=generate_uuid7(),
                tenant_id=tenant_id,
                experiment_id=experiment_id,
                artifact_type="predictions",
                storage_uri=pred_uri,
                size_bytes=len(pred_bytes),
                content_hash=pred_hash,
                metadata_json={"row_count": len(pred_df)},
            )
        )

        # 7. Record metrics in DB
        metric_records: list[MetricOrm] = []
        for metric_name, val in train_result.validation_metrics.items():
            if isinstance(val, (int, float)):
                metric_records.append(
                    MetricOrm(
                        id=generate_uuid7(),
                        experiment_id=experiment_id,
                        run_id=run_id,
                        metric_name=metric_name,
                        metric_value=float(val),
                        split="validation",
                    )
                )

        for metric_name, val in train_result.train_metrics.items():
            if isinstance(val, (int, float)):
                metric_records.append(
                    MetricOrm(
                        id=generate_uuid7(),
                        experiment_id=experiment_id,
                        run_id=run_id,
                        metric_name=metric_name,
                        metric_value=float(val),
                        split="train",
                    )
                )

        await self.metric_repo.record_metrics(metric_records)

        return {
            "experiment_id": experiment_id,
            "status": "SUCCEEDED",
            "metrics": train_result.validation_metrics,
            "artifacts": {
                "model_uri": model_uri,
                "predictions_uri": pred_uri,
            },
        }
