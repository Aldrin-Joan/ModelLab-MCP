"""Negative and boundary unit tests for dataset ingestion and validation."""

import pytest

from ml_mcp.application.datasets.validator import DatasetValidator
from ml_mcp.config import Settings
from ml_mcp.domain.errors import DatasetValidationError
from ml_mcp.domain.value_objects import DatasetFormat


def test_jagged_csv_rejected():
    """Verify CSV with inconsistent column counts per row raises DatasetValidationError."""
    validator = DatasetValidator()
    jagged_csv = b"col1,col2\nval1,val2,val3\n"
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(jagged_csv, DatasetFormat.CSV)
    assert "failed to parse" in str(exc.value).lower() or "expected" in str(exc.value).lower()


def test_corrupt_jsonl_rejected():
    """Verify JSONL with malformed JSON lines raises DatasetValidationError."""
    validator = DatasetValidator()
    corrupt_jsonl = b'{"a": 1, "b": 2}\n{not a valid json}\n'
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(corrupt_jsonl, DatasetFormat.JSONL)
    assert "failed to parse" in str(exc.value).lower()


def test_corrupt_parquet_rejected():
    """Verify corrupt Parquet file bytes raise DatasetValidationError."""
    validator = DatasetValidator()
    corrupt_parquet = b"PAR1_this_is_not_valid_parquet_binary_content"
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(corrupt_parquet, DatasetFormat.PARQUET)
    assert "failed to parse" in str(exc.value).lower()


def test_zero_row_csv_rejected():
    """Verify CSV containing only headers (0 data rows) is rejected."""
    validator = DatasetValidator()
    header_only_csv = b"feature1,feature2,target\n"
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(header_only_csv, DatasetFormat.CSV)
    assert "0 rows" in str(exc.value).lower() or "empty" in str(exc.value).lower()


def test_empty_dataset_payload_rejected():
    """Verify empty byte payload is rejected."""
    validator = DatasetValidator()
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(b"", DatasetFormat.CSV)
    assert "empty" in str(exc.value).lower()


def test_unsupported_format_rejected():
    """Verify unrecognized format raises DatasetValidationError."""
    validator = DatasetValidator()
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(b"a,b\n1,2\n", "xml")
    assert "unsupported" in str(exc.value).lower()


def test_exceeded_columns_rejected():
    """Verify dataset with columns exceeding maximum threshold is rejected."""
    validator = DatasetValidator()
    # Generate CSV with 1005 columns (threshold is 1000)
    cols = [f"col_{i}" for i in range(1005)]
    header = ",".join(cols) + "\n"
    row = ",".join(["1"] * 1005) + "\n"
    csv_bytes = (header + row).encode("utf-8")

    with pytest.raises(DatasetValidationError) as exc:
        validator.process(csv_bytes, DatasetFormat.CSV)
    assert "column count" in str(exc.value).lower() or "exceeds" in str(exc.value).lower()


def test_exceeded_upload_bytes_rejected():
    """Verify upload exceeding max_dataset_upload_bytes is rejected."""
    settings = Settings()
    settings.security.max_dataset_upload_bytes = 100  # Low threshold for test
    validator = DatasetValidator(settings=settings)

    large_payload = b"a" * 200
    with pytest.raises(DatasetValidationError) as exc:
        validator.process(large_payload, DatasetFormat.CSV)
    assert "exceeds maximum permitted limit" in str(exc.value).lower()
