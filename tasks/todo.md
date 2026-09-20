# Task List: Pre-Publish Audit Remediation

## Task 1: Add Upfront target_column and feature_columns Validation
**Description:** In `src/ml_mcp/application/experiments/service.py`, update `create_experiment` to fetch `DatasetVersionOrm` using `DatasetRepository.get_version_by_id`. Validate that `target_column` exists in `schema_json["columns"]`, and if `feature_columns` is specified, validate that all feature columns exist and that `target_column` is not included in `feature_columns`. Raise `InvalidExperimentError` if validation fails.

**Acceptance criteria:**
- [x] `create_experiment` raises `ResourceNotFoundError` if `dataset_version_id` does not exist.
- [x] `create_experiment` raises `InvalidExperimentError` if `target_column` is missing from dataset schema.
- [x] `create_experiment` raises `InvalidExperimentError` if any `feature_columns` are missing from dataset schema.
- [x] `create_experiment` raises `InvalidExperimentError` if `target_column` is in `feature_columns`.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py -k test_create_experiment_column_validation`

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/application/experiments/service.py`
**Estimated scope:** Small (1 file)

---

## Task 2: Add Upfront Validation Contract Tests
**Description:** Add contract tests in `tests/contract/test_mcp_tools.py` verifying that invalid `target_column` and `feature_columns` are rejected upfront with 422 `INVALID_EXPERIMENT`.

**Acceptance criteria:**
- [x] Contract tests assert upfront failure before any experiment is queued or run.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py`

**Dependencies:** Task 1
**Files likely touched:**
- `tests/contract/test_mcp_tools.py`
**Estimated scope:** Small (1 file)

---

## Task 3: Expose error_message and error_type in get_experiment
**Description:** In `src/ml_mcp/application/experiments/service.py`, update `get_experiment` to sort `exp.runs` by `run_number desc` / `created_at desc` so `latest_run` is the most recent run. When `latest_run.failure_reason` is present, surface `error_message` and `error_type` in the response dict.

**Acceptance criteria:**
- [x] `get_experiment` output includes `"error_message": str | None` and `"error_type": str | None`.
- [x] For failed experiments, `error_message` contains the execution error (e.g. `latest_run.failure_reason`).

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py -k test_get_experiment_failure_details`

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/application/experiments/service.py`
**Estimated scope:** Small (1 file)

---

## Task 4: Update get_experiment Tool Schema
**Description:** In `C:\Users\Aldrin Joan\.gemini\antigravity\mcp\modellab\get_experiment.json`, document `error_message` and `error_type` fields in the response properties.

**Acceptance criteria:**
- [x] Tool schema reflects `error_message` and `error_type`.

**Verification:**
- [x] File verified.

**Dependencies:** Task 3
**Files likely touched:**
- `C:\Users\Aldrin Joan\.gemini\antigravity\mcp\modellab\get_experiment.json`
**Estimated scope:** Small (1 file)

---

## Task 5: Add Contract Tests for Error Surfacing in get_experiment
**Description:** In `tests/contract/test_mcp_tools.py`, add a test that marks or executes a failed experiment and verifies `get_experiment` returns `error_message` and `error_type`.

**Acceptance criteria:**
- [x] Contract test verifies `error_message` is populated when experiment fails.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py`

**Dependencies:** Task 3, Task 4
**Files likely touched:**
- `tests/contract/test_mcp_tools.py`
**Estimated scope:** Small (1 file)

---

## Task 6: Add allow_writing_files=False to CatBoostTrainer
**Description:** In `src/ml_mcp/workers/trainers/catboost_model.py`, add `"allow_writing_files": False` to the parameters dict passed to `cb.CatBoostClassifier` and `cb.CatBoostRegressor`.

**Acceptance criteria:**
- [x] CatBoost never attempts to create `./catboost_info` on disk.
- [x] CatBoost trains cleanly on datasets with categorical columns (processed via OneHotEncoder) and numeric features.

**Verification:**
- [x] Tests pass: Unit test for CatBoost trainer.

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/workers/trainers/catboost_model.py`
**Estimated scope:** Small (1 file)

---

## Task 7: Add Unit Test for CatBoost Trainer Robustness
**Description:** Add a unit test in `tests/unit/test_trainers.py` testing `CatBoostTrainer` on both classification and regression data with categorical features, verifying no `catboost_info` directory is created.

**Acceptance criteria:**
- [x] Test confirms `allow_writing_files=False` and successful training with zero filesystem artifacts outside `TrainingResult`.

**Verification:**
- [x] Tests pass: `pytest tests/unit/test_trainers.py`

**Dependencies:** Task 6
**Files likely touched:**
- `tests/unit/test_trainers.py`
**Estimated scope:** Small (1 file)

---

## Task 8: Update Linear SVM Model Documentation
**Description:** In `src/ml_mcp/application/models/catalog_seed.py` and `Docs/Architecture.md`, update the `linear_svm` model description to explicitly document that `LinearSVC` does not natively produce probability estimates, so probability-dependent metrics (`roc_auc`, `pr_auc`, `log_loss`, `brier_score`) are omitted.

**Acceptance criteria:**
- [x] Catalog seed description for `linear_svm` mentions omitted probability metrics.
- [x] `Docs/Architecture.md` documents model metrics behavior.

**Verification:**
- [x] Tests pass: `pytest tests/unit/test_policies.py`

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/application/models/catalog_seed.py`
- `Docs/Architecture.md`
**Estimated scope:** Small (2 files)

---

## Task 9: Run Full Test Suite Pass
**Description:** Execute the entire test suite to ensure no regressions across unit, contract, and integration tests.

**Acceptance criteria:**
- [x] 100% of tests pass (104/104 passed).

**Verification:**
- [x] Tests pass: `pytest tests/`

**Dependencies:** Tasks 1-8
**Files likely touched:** None
**Estimated scope:** Verification

---

## Task 10: Linter & Formatting Pass
**Description:** Run `ruff check src tests` to confirm clean code quality.

**Acceptance criteria:**
- [x] 0 linter errors or warnings.

**Verification:**
- [x] `ruff check src tests`

**Dependencies:** Task 9
**Files likely touched:** None
**Estimated scope:** Verification
