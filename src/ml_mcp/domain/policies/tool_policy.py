"""Tool classification and security requirements."""

from enum import StrEnum

from pydantic import BaseModel

from ml_mcp.domain.policies.rbac import Scope


class ToolClass(StrEnum):
    """Policy classification for rate limiting, auditing, and access control."""

    READ = "READ"
    MUTATION = "MUTATION"
    EXPERIMENT = "EXPERIMENT"
    CONTROL = "CONTROL"
    ANALYSIS = "ANALYSIS"
    ARTIFACT = "ARTIFACT"


class ToolPolicy(BaseModel):
    """Security and rate-limiting policy governing an MCP tool."""

    tool_name: str
    tool_class: ToolClass
    required_scope: Scope
    requires_auth: bool = True
    requires_audit: bool = True
    rate_limit_category: str  # "read", "metadata", "experiment", "analysis"


TOOL_POLICIES: dict[str, ToolPolicy] = {
    # Discovery tools
    "list_models": ToolPolicy(
        tool_name="list_models",
        tool_class=ToolClass.READ,
        required_scope=Scope.MODELS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "get_model": ToolPolicy(
        tool_name="get_model",
        tool_class=ToolClass.READ,
        required_scope=Scope.MODELS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "list_model_versions": ToolPolicy(
        tool_name="list_model_versions",
        tool_class=ToolClass.READ,
        required_scope=Scope.MODELS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "list_datasets": ToolPolicy(
        tool_name="list_datasets",
        tool_class=ToolClass.READ,
        required_scope=Scope.DATASETS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "get_dataset": ToolPolicy(
        tool_name="get_dataset",
        tool_class=ToolClass.READ,
        required_scope=Scope.DATASETS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "list_dataset_versions": ToolPolicy(
        tool_name="list_dataset_versions",
        tool_class=ToolClass.READ,
        required_scope=Scope.DATASETS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    # Dataset management tools
    "register_dataset": ToolPolicy(
        tool_name="register_dataset",
        tool_class=ToolClass.MUTATION,
        required_scope=Scope.DATASETS_WRITE,
        requires_audit=True,
        rate_limit_category="experiment",
    ),
    "validate_dataset": ToolPolicy(
        tool_name="validate_dataset",
        tool_class=ToolClass.READ,
        required_scope=Scope.DATASETS_READ,
        requires_audit=True,
        rate_limit_category="metadata",
    ),
    "inspect_dataset": ToolPolicy(
        tool_name="inspect_dataset",
        tool_class=ToolClass.READ,
        required_scope=Scope.DATASETS_READ,
        requires_audit=True,
        rate_limit_category="metadata",
    ),
    # Experiment tools
    "create_experiment": ToolPolicy(
        tool_name="create_experiment",
        tool_class=ToolClass.EXPERIMENT,
        required_scope=Scope.EXPERIMENTS_CREATE,
        requires_audit=True,
        rate_limit_category="experiment",
    ),
    "get_experiment": ToolPolicy(
        tool_name="get_experiment",
        tool_class=ToolClass.READ,
        required_scope=Scope.EXPERIMENTS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "cancel_experiment": ToolPolicy(
        tool_name="cancel_experiment",
        tool_class=ToolClass.CONTROL,
        required_scope=Scope.EXPERIMENTS_CANCEL,
        requires_audit=True,
        rate_limit_category="experiment",
    ),
    "list_experiments": ToolPolicy(
        tool_name="list_experiments",
        tool_class=ToolClass.READ,
        required_scope=Scope.EXPERIMENTS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    # Result tools
    "get_experiment_metrics": ToolPolicy(
        tool_name="get_experiment_metrics",
        tool_class=ToolClass.READ,
        required_scope=Scope.EXPERIMENTS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "get_experiment_predictions": ToolPolicy(
        tool_name="get_experiment_predictions",
        tool_class=ToolClass.ARTIFACT,
        required_scope=Scope.ARTIFACTS_READ,
        requires_audit=True,
        rate_limit_category="metadata",
    ),
    "list_experiment_artifacts": ToolPolicy(
        tool_name="list_experiment_artifacts",
        tool_class=ToolClass.READ,
        required_scope=Scope.ARTIFACTS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    "read_experiment_artifact": ToolPolicy(
        tool_name="read_experiment_artifact",
        tool_class=ToolClass.ARTIFACT,
        required_scope=Scope.ARTIFACTS_READ,
        requires_audit=True,
        rate_limit_category="metadata",
    ),
    "compare_experiments": ToolPolicy(
        tool_name="compare_experiments",
        tool_class=ToolClass.READ,
        required_scope=Scope.EXPERIMENTS_READ,
        requires_audit=False,
        rate_limit_category="read",
    ),
    # Analysis tools
    "analyze_experiment": ToolPolicy(
        tool_name="analyze_experiment",
        tool_class=ToolClass.ANALYSIS,
        required_scope=Scope.ANALYSIS_CREATE,
        requires_audit=True,
        rate_limit_category="analysis",
    ),
    "analyze_model_errors": ToolPolicy(
        tool_name="analyze_model_errors",
        tool_class=ToolClass.ANALYSIS,
        required_scope=Scope.ANALYSIS_CREATE,
        requires_audit=True,
        rate_limit_category="analysis",
    ),
    "check_experiment_validity": ToolPolicy(
        tool_name="check_experiment_validity",
        tool_class=ToolClass.ANALYSIS,
        required_scope=Scope.ANALYSIS_CREATE,
        requires_audit=True,
        rate_limit_category="analysis",
    ),
}
