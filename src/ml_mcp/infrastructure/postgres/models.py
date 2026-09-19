"""SQLAlchemy 2.x ORM models mapping the complete ModelLab control-plane schema."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7, utc_now

# Universal JSON type: native JSONB for PostgreSQL, automatic JSON serializer for SQLite
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class TenantOrm(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now, nullable=False)

    principals: Mapped[list["PrincipalOrm"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    projects: Mapped[list["ProjectOrm"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class PrincipalOrm(Base):
    __tablename__ = "principals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    scopes: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    tenant: Mapped["TenantOrm"] = relationship(back_populates="principals")

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_principals_tenant_username"),
        Index("ix_principals_tenant_created", "tenant_id", "created_at"),
    )


class ProjectOrm(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    tenant: Mapped["TenantOrm"] = relationship(back_populates="projects")
    datasets: Mapped[list["DatasetOrm"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    experiments: Mapped[list["ExperimentOrm"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_projects_tenant_name"),
        Index("ix_projects_tenant_created", "tenant_id", "created_at"),
    )


class ModelOrm(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, default="system")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    publisher: Mapped[str] = mapped_column(String(128), default="ModelLab", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    versions: Mapped[list["ModelVersionOrm"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_models_tenant_created", "tenant_id", "created_at"),)


class ModelVersionOrm(Base):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("models.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    container_image_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supported_task_types: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False)
    hyperparameters_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    model: Mapped["ModelOrm"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_versions_model_version"),
        Index("ix_model_versions_created", "created_at"),
    )


class DatasetOrm(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    project: Mapped["ProjectOrm"] = relationship(back_populates="datasets")
    versions: Mapped[list["DatasetVersionOrm"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_datasets_project_name"),
        Index("ix_datasets_tenant_created", "tenant_id", "created_at"),
        Index("ix_datasets_project_created", "project_id", "created_at"),
    )


class DatasetVersionOrm(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="VALIDATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    dataset: Mapped["DatasetOrm"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_dataset_version"),
        Index("ix_dataset_versions_hash", "content_hash"),
    )


class ExperimentOrm(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=False
    )
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False)
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["ProjectOrm"] = relationship(back_populates="experiments")
    dataset_version: Mapped["DatasetVersionOrm"] = relationship()
    model_version: Mapped["ModelVersionOrm"] = relationship()
    runs: Mapped[list["ExperimentRunOrm"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["MetricOrm"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["ArtifactOrm"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    analysis: Mapped["AnalysisRunOrm | None"] = relationship(
        back_populates="experiment", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_experiments_tenant_created", "tenant_id", "created_at"),
        Index("ix_experiments_project_created", "project_id", "created_at"),
        Index("ix_experiments_status_created", "status", "created_at"),
        Index("ix_experiments_idempotency", "tenant_id", "project_id", "idempotency_key"),
    )


class ExperimentRunOrm(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    run_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    experiment: Mapped["ExperimentOrm"] = relationship(back_populates="runs")
    metrics: Mapped[list["MetricOrm"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_experiment_runs_experiment", "experiment_id"),)


class MetricOrm(Base):
    __tablename__ = "metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    split: Mapped[str] = mapped_column(
        String(32), default="validation", nullable=False
    )  # train, validation, test
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    experiment: Mapped["ExperimentOrm"] = relationship(back_populates="metrics")
    run: Mapped["ExperimentRunOrm"] = relationship(back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_experiment_name", "experiment_id", "metric_name"),
        Index("ix_metrics_run", "run_id"),
    )


class AnalysisRunOrm(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    experiment: Mapped["ExperimentOrm"] = relationship(back_populates="analysis")

    __table_args__ = (Index("ix_analysis_tenant_created", "tenant_id", "created_at"),)


class ArtifactOrm(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # model, predictions, metrics_report, etc.
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    experiment: Mapped["ExperimentOrm"] = relationship(back_populates="artifacts")

    __table_args__ = (
        Index("ix_artifacts_experiment", "experiment_id"),
        Index("ix_artifacts_tenant_created", "tenant_id", "created_at"),
    )


class OutboxEventOrm(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING, DELIVERED, FAILED
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (Index("ix_outbox_status_scheduled", "status", "scheduled_at"),)


class AuditEventOrm(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid7)
    timestamp: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False)  # SUCCESS, DENIED, ERROR
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_audit_tenant_timestamp", "tenant_id", "timestamp"),
        Index("ix_audit_principal_timestamp", "principal_id", "timestamp"),
    )
