"""Unit test verifying all SQLAlchemy declarative ORM models and schema creation."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.models import (
    TenantOrm,
    PrincipalOrm,
    ProjectOrm,
    ModelOrm,
    ModelVersionOrm,
    DatasetOrm,
    DatasetVersionOrm,
    ExperimentOrm,
    ExperimentRunOrm,
    MetricOrm,
    AnalysisRunOrm,
    ArtifactOrm,
    OutboxEventOrm,
    AuditEventOrm,
)


def test_uuid7_generation():
    id1 = generate_uuid7()
    id2 = generate_uuid7()
    assert len(id1) == 36
    assert len(id2) == 36
    assert id1 != id2
    # UUIDv7 contains version '7' in the 13th character
    assert id1[14] == "7"
    assert id2[14] == "7"


@pytest.mark.asyncio
async def test_schema_creation_in_memory():
    # Use SQLite async in-memory to test full DDL generation of all 14 tables
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Verify all expected tables exist in metadata
    expected_tables = {
        "tenants",
        "principals",
        "projects",
        "models",
        "model_versions",
        "datasets",
        "dataset_versions",
        "experiments",
        "experiment_runs",
        "metrics",
        "analysis_runs",
        "artifacts",
        "outbox_events",
        "audit_events",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))
    await engine.dispose()
