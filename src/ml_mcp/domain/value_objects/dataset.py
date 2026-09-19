"""Dataset value objects and schema contracts."""

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class DatasetFormat(StrEnum):
    """Allowed tabular dataset formats."""

    CSV = "csv"
    PARQUET = "parquet"
    JSONL = "jsonl"


class FeatureType(StrEnum):
    """Canonical feature types inferred and used in ML preprocessing."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TEXT = "text"


class ColumnSchema(BaseModel):
    """Schema and statistical metadata for a single dataset column."""

    name: str = Field(..., min_length=1)
    feature_type: FeatureType
    nullable: bool = True
    null_count: int = Field(default=0, ge=0)
    unique_count: int = Field(default=0, ge=0)
    sample_values: list[Any] = Field(default_factory=list)


class DatasetSchema(BaseModel):
    """Complete dataset schema structure with content digest and profile."""

    columns: list[ColumnSchema]
    row_count: int = Field(..., ge=0)
    column_count: int = Field(..., ge=1)
    size_bytes: int = Field(..., ge=0)
    content_hash: str = Field(..., description="SHA-256 content hash of canonicalized dataset")

    @field_validator("columns")
    @classmethod
    def validate_unique_column_names(cls, v: list[ColumnSchema]) -> list[ColumnSchema]:
        names = [col.name.lower() for col in v]
        if len(names) != len(set(names)):
            raise ValueError("Dataset schema contains duplicate column names (case-insensitive)")
        return v

    def get_column(self, name: str) -> ColumnSchema | None:
        name_lower = name.lower()
        for col in self.columns:
            if col.name.lower() == name_lower:
                return col
        return None
