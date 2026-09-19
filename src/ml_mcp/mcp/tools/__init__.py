"""MCP tools module."""

from ml_mcp.mcp.tools.analysis import (
    handle_analyze_experiment,
    handle_analyze_model_errors,
    handle_check_experiment_validity,
)
from ml_mcp.mcp.tools.datasets import (
    handle_inspect_dataset,
    handle_register_dataset,
    handle_validate_dataset,
)
from ml_mcp.mcp.tools.discovery import (
    handle_get_dataset,
    handle_get_model,
    handle_list_dataset_versions,
    handle_list_datasets,
    handle_list_model_versions,
    handle_list_models,
)
from ml_mcp.mcp.tools.experiments import (
    handle_cancel_experiment,
    handle_create_experiment,
    handle_get_experiment,
    handle_list_experiments,
)
from ml_mcp.mcp.tools.projects import (
    handle_create_project,
    handle_list_projects,
)
from ml_mcp.mcp.tools.results import (
    handle_compare_experiments,
    handle_get_experiment_metrics,
    handle_get_experiment_predictions,
    handle_list_experiment_artifacts,
    handle_read_experiment_artifact,
)

__all__ = [
    "handle_create_project",
    "handle_list_projects",
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
