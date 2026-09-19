"""MCP Prompts providing guided workflows for agentic experimentation."""


def experiment_design_prompt(dataset_description: str, task_type: str) -> str:
    """Prompt guiding agents to design high-yield ML experiments."""
    return f"""You are the ModelLab ML Experimentation Architect.
Task: Design a rigorous, leak-free experimentation plan.

Dataset Description:
{dataset_description}

Task Type:
{task_type}

Guidelines:
1. Select 2-3 candidate architectures from approved tabular models: Logistic Regression, Random Forest, XGBoost, LightGBM, CatBoost, Linear SVM, MLP.
2. Recommend appropriate split strategy (Stratified K-Fold for imbalanced classification, Time Series Split for temporal data).
3. Specify primary and secondary evaluation metrics (e.g. PR AUC for severe class imbalance, ROC AUC for balanced ranking).
4. Propose non-overlapping hyperparameter variations to test.

Use `list_models` and `get_model` to inspect hyperparameter bounds, then submit via `create_experiment`.
"""


def error_diagnosis_prompt(experiment_id: str, problem_summary: str) -> str:
    """Prompt assisting agents in diagnosing training regressions or anomalies."""
    return f"""You are the ModelLab Diagnostic Auditor.
Task: Inspect model performance anomalies for Experiment: {experiment_id}

Problem Summary:
{problem_summary}

Step-by-step diagnostic workflow:
1. Call `get_experiment_metrics` for both train and validation splits to evaluate the generalization gap.
2. Call `analyze_experiment` to inspect automated overfitting and leakage signals.
3. Call `analyze_model_errors` to review false positives vs false negatives and residual skew.
4. Formulate 2 actionable next experiments addressing the root cause.
"""
