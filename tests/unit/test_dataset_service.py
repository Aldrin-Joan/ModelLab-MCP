"""Unit tests for dataset validator and service."""

import pytest
from unittest.mock import MagicMock
from ml_mcp.application.datasets.validator import DatasetValidator
from ml_mcp.application.datasets.service import DatasetService
from ml_mcp.domain.errors import DatasetValidationError
from ml_mcp.domain.value_objects import DatasetFormat, FeatureType
from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.session import DatabaseManager
from ml_mcp.infrastructure.postgres.models import TenantOrm, ProjectOrm


def test_csv_validation_and_schema_extraction():
    validator = DatasetValidator()
    csv_bytes = b"id,age,income,churn,signup_date\n1,25,50000.0,0,2023-01-01\n2,40,95000.5,1,2023-01-02\n3,33,72000.0,0,2023-01-03\n"

    df, parquet_bytes, schema = validator.process(csv_bytes, DatasetFormat.CSV)
    assert len(df) == 3
    assert schema.row_count == 3
    assert schema.column_count == 5
    assert schema.size_bytes == len(parquet_bytes)
    assert schema.content_hash.startswith("sha256:")

    age_col = schema.get_column("age")
    assert age_col is not None
    assert age_col.feature_type == FeatureType.NUMERIC
    assert age_col.nullable is False


def test_empty_dataset_rejected():
    validator = DatasetValidator()
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(b"", DatasetFormat.CSV)
    assert "empty" in str(exc.value)


def test_malformed_csv_rejected():
    validator = DatasetValidator()
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(b"not,a,valid,csv\n1,2\n3", DatasetFormat.PARQUET)
    assert "Failed to parse" in str(exc.value)


@pytest.mark.asyncio
async def test_dataset_service_registration():
    db_mgr = DatabaseManager()
    db_mgr.initialize(custom_url="sqlite+aiosqlite:///file:dsservdb?mode=memory&cache=shared&uri=true")
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tenant_id = generate_uuid7()
    project_id = generate_uuid7()

    async with db_mgr.session() as sess:
        t = TenantOrm(id=tenant_id, name="Tenant DS")
        p = ProjectOrm(id=project_id, tenant_id=tenant_id, name="Project DS")
        sess.add_all([t, p])

    mock_storage = MagicMock()
    mock_storage.get_dataset_key.return_value = "tenants/t/datasets/d/v/data.parquet"
    mock_storage.put_object.return_value = ("s3://bucket/tenants/t/datasets/d/v/data.parquet", "sha256:abc")
    mock_storage.generate_presigned_get_url.return_value = "https://s3.example.com/download"

    csv_data = b"feature1,feature2,target\n1.2,3.4,0\n5.6,7.8,1\n"

    async with db_mgr.session() as sess:
        service = DatasetService(session=sess, storage_service=mock_storage)
        result = await service.register_dataset(
            tenant_id=tenant_id,
            project_id=project_id,
            name="Test Dataset",
            description="Integration test dataset",
            data_format=DatasetFormat.CSV,
            raw_bytes=csv_data,
        )

        assert result["name"] == "Test Dataset"
        assert result["row_count"] == 2
        assert result["column_count"] == 3

        # List datasets
        ds_list = await service.list_datasets(tenant_id, project_id)
        assert len(ds_list) == 1
        assert ds_list[0]["name"] == "Test Dataset"

    await db_mgr.close()
