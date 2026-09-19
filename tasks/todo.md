# Task List: Test Report Remediation & Downstream Verification

## Task 1: Add PROJECTS_READ and PROJECTS_WRITE Scopes to RBAC Matrix
**Description:** Update `src/ml_mcp/domain/policies/rbac.py` to add `PROJECTS_READ` and `PROJECTS_WRITE` scopes to `Scope(StrEnum)` and map them into the role permission sets for `Role.VIEWER` (read), `Role.RESEARCHER` (read/write), `Role.OPERATOR` (read/write), and `Role.ADMIN` (all).

**Acceptance criteria:**
- [x] `Scope.PROJECTS_READ` ("ml:projects:read") and `Scope.PROJECTS_WRITE` ("ml:projects:write") are defined.
- [x] Roles have appropriate project scopes assigned in `ROLE_PERMISSIONS`.

**Verification:**
- [x] Tests pass: `pytest tests/unit/domain/test_policies.py` or equivalent.

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/domain/policies/rbac.py`
**Estimated scope:** Small (1 file)

---

## Task 2: Implement ProjectRepository
**Description:** Implement `ProjectRepository` in `src/ml_mcp/infrastructure/postgres/repositories/projects.py` to handle project querying, creation, listing with pagination, and `get_or_create_default_project` for a tenant.

**Acceptance criteria:**
- [x] `get_project(tenant_id: str, project_id: str) -> ProjectOrm | None` retrieves project belonging to tenant.
- [x] `create_project(project: ProjectOrm) -> ProjectOrm` persists new project.
- [x] `list_projects(tenant_id: str, limit: int = 50, offset: int = 0) -> list[ProjectOrm]` lists tenant projects.
- [x] `get_or_create_default_project(tenant_id: str) -> ProjectOrm` guarantees existence of default project.

**Verification:**
- [x] Tests pass: `pytest tests/integration/test_repositories.py`

**Dependencies:** Task 1
**Files likely touched:**
- `src/ml_mcp/infrastructure/postgres/repositories/projects.py`
- `src/ml_mcp/infrastructure/postgres/repositories/__init__.py`
**Estimated scope:** Small (2 files)

---

## Task 3: Implement ProjectService
**Description:** Implement `ProjectService` in `src/ml_mcp/application/projects/service.py` to coordinate project operations, return clean dictionary payloads, and support ensuring the default project during server startup.

**Acceptance criteria:**
- [x] `create_project(tenant_id: str, name: str, description: str = "") -> dict[str, Any]` creates and returns project.
- [x] `list_projects(tenant_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]` returns paginated project list.
- [x] `get_project(tenant_id: str, project_id: str) -> dict[str, Any]` retrieves project or raises `ResourceNotFoundError`.
- [x] `ensure_default_project(tenant_id: str) -> dict[str, Any]` seeds `default-project` ("Default Project") if not present.

**Verification:**
- [x] Tests pass: Service unit tests.

**Dependencies:** Task 2
**Files likely touched:**
- `src/ml_mcp/application/projects/service.py`
- `src/ml_mcp/application/projects/__init__.py`
**Estimated scope:** Small (2 files)

---

## Checkpoint 1: Foundation (Tasks 1-3)
- [x] RBAC policy, ProjectRepository, and ProjectService are implemented and tested.

---

## Task 4: Fix Hardcoded Dataset Format in DatasetService
**Description:** In `src/ml_mcp/application/datasets/service.py`, fix `register_dataset` where `format="parquet"` is hardcoded. Ensure the caller's `data_format` (e.g. `"csv"`, `"jsonl"`, `"parquet"`) is normalized and preserved in `DatasetOrm(format=fmt)`.

**Acceptance criteria:**
- [x] `DatasetOrm(format=fmt)` stores the actual input data format instead of hardcoded `"parquet"`.
- [x] Tested with `"csv"` format: database record reflects `"csv"`.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py`

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/application/datasets/service.py`
**Estimated scope:** Small (1 file)

---

## Task 5: Harden Base64 Decoding & Malformed Input Handling
**Description:** In `src/ml_mcp/mcp/tools/datasets.py`, use `base64.b64decode(data_base64, validate=True)` and catch `binascii.Error`, raising `InvalidInputError("Invalid base64 payload")`. In `src/ml_mcp/application/datasets/validator.py`, ensure truncated CSV/JSONL or malformed encoding is consistently detected and rejected with `DatasetValidationError`.

**Acceptance criteria:**
- [x] Malformed or truncated base64 strings raise `InvalidInputError`.
- [x] Malformed/corrupted tabular payloads raise `DatasetValidationError`.

**Verification:**
- [x] Tests pass: Unit/contract tests with malformed inputs.

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/mcp/tools/datasets.py`
- `src/ml_mcp/application/datasets/validator.py`
**Estimated scope:** Small (2 files)

---

## Task 6: Assign Distinct Container Image Digests per Model Family
**Description:** In `src/ml_mcp/application/models/catalog_seed.py`, replace the shared duplicate container digest `sha256:7f83b1657ff1...` with distinct, deterministic SHA-256 digests for each of the 7 approved models.

**Acceptance criteria:**
- [x] Each of the 7 models has a unique, valid 64-hex-character SHA-256 container image digest.
- [x] No two models share the same image digest.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py`

**Dependencies:** None
**Files likely touched:**
- `src/ml_mcp/application/models/catalog_seed.py`
**Estimated scope:** Small (1 file)

---

## Checkpoint 2: Service Layer (Tasks 4-6)
- [x] Dataset format is preserved on registration.
- [x] Malformed base64 is caught and cleanly reported.
- [x] All 7 models have distinct image digests.

---

## Task 7: Implement Project MCP Tool Handlers
**Description:** In `src/ml_mcp/mcp/tools/projects.py`, implement `handle_create_project` and `handle_list_projects` with RBAC enforcement (`Scope.PROJECTS_WRITE`, `Scope.PROJECTS_READ`).

**Acceptance criteria:**
- [x] `handle_create_project` enforces `PROJECTS_WRITE` and calls `ProjectService.create_project`.
- [x] `handle_list_projects` enforces `PROJECTS_READ` and calls `ProjectService.list_projects`.

**Verification:**
- [x] Tests pass: Tool invocation tests.

**Dependencies:** Task 1, Task 3
**Files likely touched:**
- `src/ml_mcp/mcp/tools/projects.py`
- `src/ml_mcp/mcp/tools/__init__.py`
**Estimated scope:** Small (2 files)

---

## Task 8: Enforce Consistent Project Validation in Experiments Tools
**Description:** In `src/ml_mcp/mcp/tools/experiments.py`, update `handle_list_experiments` to validate that when `project_id` is supplied, the project exists for the tenant (or raise `ResourceNotFoundError`).

**Acceptance criteria:**
- [x] Supplying a non-existent `project_id` to `list_experiments` raises `ResourceNotFoundError`.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py`

**Dependencies:** Task 2
**Files likely touched:**
- `src/ml_mcp/mcp/tools/experiments.py`
**Estimated scope:** Small (1 file)

---

## Task 9: Register Tools, Startup Seed, and Sanitize Database Exceptions
**Description:** In `src/ml_mcp/server/app.py`:
1. Register `create_project` and `list_projects` tools with descriptions and docstrings (expanding tool catalog from 21 to 23).
2. In `app_lifespan`, call `ProjectService.ensure_default_project("default-tenant")`.
3. In `_execute_secured`, intercept SQLAlchemy `IntegrityError` / `DBAPIError` and convert foreign key violations to `ResourceNotFoundError` and uniqueness/constraint failures to `InvalidInputError`, sanitizing raw SQL queries and parameter dumps.

**Acceptance criteria:**
- [x] `create_server()` registers `create_project` and `list_projects`.
- [x] Server startup creates `default-project` under `default-tenant`.
- [x] Foreign key / database integrity errors return sanitized domain errors without leaking SQL or parameters.

**Verification:**
- [x] Tests pass: Server startup and error handling tests.

**Dependencies:** Task 7, Task 8
**Files likely touched:**
- `src/ml_mcp/server/app.py`
**Estimated scope:** Small (1 file)

---

## Checkpoint 3: Server Layer (Tasks 7-9)
- [x] All 23 tools are registered.
- [x] Default project is seeded.
- [x] SQL leakage is eliminated.

---

## Task 10: Update Contract Tests for 23 Tools & Project Tools
**Description:** In `tests/contract/test_mcp_tools.py`, update `test_tool_catalog_contract` to expect 23 tools including `create_project` and `list_projects`. Add tests for `create_project` and `list_projects`, and assert that `register_dataset` preserves the specified format in the returned schema/ORM.

**Acceptance criteria:**
- [x] `test_tool_catalog_contract` passes with 23 tools.
- [x] `create_project` and `list_projects` are tested via `server.call_tool`.
- [x] Dataset format is asserted to be `"csv"`.

**Verification:**
- [x] Tests pass: `pytest tests/contract/test_mcp_tools.py`

**Dependencies:** Task 9
**Files likely touched:**
- `tests/contract/test_mcp_tools.py`
**Estimated scope:** Small (1 file)

---

## Task 11: End-to-End Downstream Verification Test Suite
**Description:** Create `tests/integration/test_test_report_remediation.py` testing against real PostgreSQL database:
1. Creating a project and listing projects.
2. Using default seeded project `default-project`.
3. Registering CSV dataset and verifying format is `"csv"`.
4. Testing all 8 downstream tools that were previously blocked in the report:
   - `create_experiment`
   - `list_experiment_artifacts`
   - `read_experiment_artifact`
   - `analyze_experiment`
   - `analyze_model_errors`
   - `get_experiment_predictions`
   - `check_experiment_validity`
   - `list_dataset_versions`
5. Verifying information disclosure fix (non-existent project_id returns sanitized `ResourceNotFoundError`, zero raw SQL leaked).
6. Verifying distinct container image digests across model families.
7. Verifying malformed base64 handling in `validate_dataset`.

**Acceptance criteria:**
- [x] All 8 downstream tools execute successfully.
- [x] Information disclosure is prevented.
- [x] 100% tests pass.

**Verification:**
- [x] Tests pass: `pytest tests/integration/test_test_report_remediation.py`
- [x] Full suite pass: `pytest tests/` (101/101 passed)
- [x] Linter pass: `ruff check src tests` (All checks passed)

**Dependencies:** Task 10
**Files likely touched:**
- `tests/integration/test_test_report_remediation.py`
**Estimated scope:** Medium (1-2 files)

---

## Checkpoint 4: Complete Verification
- [x] 100% of tests pass across contract and integration suites (101/101 passed).
- [x] Ruff check passes with 0 errors.
- [x] All 6 issues from the test report are fully resolved and verified.
