"""MCP tools module."""

from ml_mcp.mcp.tools.discovery import (
    handle_list_models,
    handle_get_model,
    handle_list_model_versions,
    handle_list_datasets,
    handle_get_dataset,
    handle_list_dataset_versions,
)
from ml_mcp.mcp.tools.datasets import (
    handle_register_dataset,
    handle_validate_dataset,
    handle_inspect_dataset,
)
from ml_mcp.mcp.tools.experiments import (
    handle_create_experiment,
    handle_get_experiment,
    handle_cancel_experiment,
    handle_list_experiments,
)
from ml_mcp.mcp.tools.results import (
    handle_get_experiment_metrics,
    handle_get_experiment_predictions,
    handle_list_experiment_artifacts,
    handle_read_experiment_artifact,
    handle_compare_experiments,
)
from ml_mcp.mcp.tools.analysis import (
    handle_analyze_experiment,
    handle_analyze_model_errors,
    handle_check_experiment_validity,
)

__all__ = [
    "handle_list_models",
    "handle_get_model",
    "handle_list_model_versions",
    "handle_list_datasets",
    "handle_get_dataset",
    "handle_list_dataset_versions",
    "handle_register_dataset",
    "handle_validate_dataset",
    "handle_inspect_dataset",
    "handle_create_experiment",
    "handle_get_experiment",
    "handle_cancel_experiment",
    "handle_list_experiments",
    "handle_get_experiment_metrics",
    "handle_get_experiment_predictions",
    "handle_list_experiment_artifacts",
    "handle_read_experiment_artifact",
    "handle_compare_experiments",
    "handle_analyze_experiment",
    "handle_analyze_model_errors",
    "handle_check_experiment_validity",
]
