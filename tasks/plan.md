# Implementation Plan: ModelLab MCP Pre-Publish Audit Remediation

## Overview
This plan resolves the critical model bug, observability gap, upfront validation omission, and documentation notes identified in the **ModelLab MCP Full Pre-Publish Audit (2026-09-20)**:
1. **CatBoost Model Bug**: Fix `catboost_info` working directory crash in containerized/unprivileged environments by setting `allow_writing_files=False`, ensuring CatBoost trains reliably on datasets with categorical columns and numeric features.
2. **Observability Gap**: Surface `error_message` and `error_type` in `get_experiment` and diagnostic responses for `FAILED` experiments so users can self-diagnose failures without backend access.
3. **Upfront Dataset Column Validation**: Validate `target_column` and `feature_columns` against the dataset version's schema at `create_experiment` time, rejecting nonexistent columns upfront before queuing.
4. **Linear SVM Metrics Documentation**: Clarify why `linear_svm` omits probability-dependent metrics (`roc_auc`, `pr_auc`, `log_loss`, `brier_score`) in the model catalog and documentation.

---

## Architecture Decisions
1. **CatBoost File Writing**:
   - In `src/ml_mcp/workers/trainers/catboost_model.py`, explicitly set `"allow_writing_files": False` in hyperparameters for both `CatBoostClassifier` and `CatBoostRegressor`. This prevents CatBoost from attempting to create `./catboost_info` in `/app`, eliminating permission collisions and multi-worker crashes.
2. **Observability in `get_experiment`**:
   - In `ExperimentService.get_experiment`, order `exp.runs` by `run_number desc` / `created_at desc` to guarantee the latest run is selected.
   - Extract `error_message` from `latest_run.failure_reason`.
   - Extract `error_type` (derived from the exception message or type prefix).
   - Expose `error_message: str | None` and `error_type: str | None` in `get_experiment` output.
   - Update `get_experiment.json` FastMCP schema to document these fields.
3. **Upfront Dataset Column Validation**:
   - In `ExperimentService.create_experiment`, load `DatasetVersionOrm` via `DatasetRepository.get_version_by_id(tenant_id, dataset_version_id)`.
   - Extract `available_columns = [col["name"] for col in dsv.schema_json.get("columns", [])]`.
   - If `target_column not in available_columns`: raise `InvalidExperimentError(f"Target column '{target_column}' not found in dataset '{dsv.dataset_id}' version '{dsv.version}'. Available columns: {available_columns}")`.
   - If `feature_columns` is specified:
     - Check `missing = [c for c in feature_columns if c not in available_columns]`: if missing, raise `InvalidExperimentError(...)`.
     - Check `if target_column in feature_columns`: raise `InvalidExperimentError("Target column cannot be included in feature_columns")`.
     - Check `if len(feature_columns) == 0`: raise `InvalidExperimentError("feature_columns list cannot be empty when specified")`.
4. **Linear SVM Metric Transparency**:
   - In `src/ml_mcp/application/models/catalog_seed.py`, update `linear_svm` description to document that `LinearSVC` does not natively output probabilities, so probability-dependent metrics (`roc_auc`, `pr_auc`, `log_loss`) are omitted.

---

## Task List

### Phase 1: Upfront Dataset Column Validation
- [ ] Task 1: Add upfront `target_column` and `feature_columns` validation in `ExperimentService.create_experiment` (`src/ml_mcp/application/experiments/service.py`).
- [ ] Task 2: Add contract/unit tests in `tests/contract/test_mcp_tools.py` verifying `create_experiment` rejects missing `target_column` and missing `feature_columns` upfront with 422 `INVALID_EXPERIMENT`.

### Phase 2: Observability Gap — Surfacing Error Details
- [ ] Task 3: Expose `error_message` and `error_type` on `get_experiment` in `src/ml_mcp/application/experiments/service.py` and ensure runs are sorted descending.
- [ ] Task 4: Update `get_experiment.json` FastMCP tool schema.
- [ ] Task 5: Add tests in `tests/contract/test_mcp_tools.py` verifying that a failed experiment returns `error_message` and `error_type` in `get_experiment`.

### Phase 3: CatBoost Trainer Robustness
- [ ] Task 6: Add `"allow_writing_files": False` in `src/ml_mcp/workers/trainers/catboost_model.py`.
- [ ] Task 7: Add unit test in `tests/unit/workers/test_catboost_trainer.py` verifying CatBoost trains on datasets with categorical columns without writing `./catboost_info`.

### Phase 4: Model Catalog & Documentation Note
- [ ] Task 8: Update `linear_svm` model description in `src/ml_mcp/application/models/catalog_seed.py` and `Docs/Architecture.md`.

### Phase 5: Verification & Full Suite Pass
- [ ] Task 9: Run full test suite with `pytest tests/` (all 100+ tests pass).
- [ ] Task 10: Run `ruff check src tests` to verify zero lint/formatting regressions.

---

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Older dataset versions without `columns` in `schema_json` | Low | Fall back gracefully if `columns` is missing in `schema_json` by skipping upfront column check or treating as empty list. |
| Upfront validation adds a database query to `create_experiment` | Low | `DatasetRepository.get_version_by_id` is an indexed primary key lookup on `dataset_versions` (< 1ms). |
| Existing tests creating experiments with dummy datasets | Med | Ensure existing test fixtures register valid dataset versions with matching column names. |
