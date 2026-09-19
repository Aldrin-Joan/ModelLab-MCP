# Implementation Plan: ModelLab MCP Test Report Remediation & Project Bootstrap

## Overview
This plan addresses all issues, data-integrity bugs, security information disclosures, and downstream blockages identified in the ModelLab MCP Test Report (2026-09-19).
Specifically, it introduces first-class Project management (`create_project`, `list_projects`) and automatic default project seeding (`default-project`), fixes the hardcoded format bug in dataset registration, sanitizes database exceptions to eliminate information disclosure, enforces consistent project validation across read/write endpoints, hardens dataset input/base64 decoding against malformed payloads, assigns distinct container image digests to each approved model family, and unblocks and verifies all 8 downstream tools through comprehensive contract and integration tests.

## Architecture Decisions
1. **First-Class Project Lifecycle**:
   - Add `ProjectRepository` in `src/ml_mcp/infrastructure/postgres/repositories/projects.py`.
   - Add `ProjectService` in `src/ml_mcp/application/projects/service.py`.
   - Expose `create_project` and `list_projects` FastMCP tools (scoped with `PROJECTS_WRITE` and `PROJECTS_READ` in `rbac.py`).
   - Auto-seed `default-project` ("Default Project") for `default-tenant` during server lifespan startup so the server is functional immediately out-of-the-box.
2. **Dataset Format Preservation**:
   - In `DatasetService.register_dataset`, dynamically map `data_format` (str or enum) to lower-case string (e.g., `"csv"`, `"parquet"`, `"jsonl"`) and store it in `DatasetOrm(format=fmt)`.
3. **Database Exception Sanitization**:
   - In `_execute_secured` (`src/ml_mcp/server/app.py`), intercept SQLAlchemy `IntegrityError` and `DBAPIError`.
   - Translate foreign key constraint failures (e.g., non-existent `project_id`, `dataset_id`) into `ResourceNotFoundError`.
   - Translate unique constraint violations and malformed data into `InvalidInputError`.
   - Strip all raw SQL, table names, and parameter dumps to prevent information leakage.
4. **Consistent Project Existence Validation**:
   - Validate project existence in `list_experiments` when `project_id` is supplied: if the project does not exist under the tenant, raise `ResourceNotFoundError` rather than returning `[]`.
5. **Strict Base64 & Malformed Input Handling**:
   - Use `base64.b64decode(data_base64, validate=True)` with explicit `binascii.Error` trapping in `handle_register_dataset` and `handle_validate_dataset`, converting decode failures into `InvalidInputError`.
   - Ensure `DatasetValidator` strictly flags malformed or truncated CSV/JSONL/Parquet payloads.
6. **Deterministic Per-Family Model Digests**:
   - In `src/ml_mcp/application/models/catalog_seed.py`, replace the identical placeholder digest with distinct, deterministic SHA-256 digests computed per model family.
7. **Downstream Verification**:
   - Exercise the entire end-to-end pipeline: Project creation -> Dataset registration -> Dataset validation/inspection -> Experiment creation -> Artifact listing/reading -> Metrics & predictions retrieval -> Experiment analysis & error diagnosis.

## Task List

### Phase 1: Core Domain, RBAC & Repositories
- [ ] Task 1: Add `PROJECTS_READ` and `PROJECTS_WRITE` scopes to RBAC policy matrix in `src/ml_mcp/domain/policies/rbac.py`.
- [ ] Task 2: Implement `ProjectRepository` in `src/ml_mcp/infrastructure/postgres/repositories/projects.py` with get, create, list, and get_or_create_default methods.
- [ ] Task 3: Implement `ProjectService` in `src/ml_mcp/application/projects/service.py`.

### Checkpoint: Foundation
- [ ] Unit tests for ProjectRepository and ProjectService pass.

### Phase 2: Service Bug Fixes & Hardening
- [ ] Task 4: Fix hardcoded `format="parquet"` bug in `src/ml_mcp/application/datasets/service.py`.
- [ ] Task 5: Harden base64 decoding (`validate=True`) and input validation in `src/ml_mcp/mcp/tools/datasets.py` and `validator.py`.
- [ ] Task 6: Assign distinct deterministic container image digests to each approved model family in `src/ml_mcp/application/models/catalog_seed.py`.

### Checkpoint: Service Layer
- [ ] Dataset registration correctly stores format ("csv", etc.).
- [ ] Model versions return distinct image digests.
- [ ] Malformed base64/dataset payloads raise clean validation errors.

### Phase 3: FastMCP Tools, Lifespan Seed & Exception Sanitization
- [ ] Task 7: Implement `handle_create_project` and `handle_list_projects` in `src/ml_mcp/mcp/tools/projects.py`.
- [ ] Task 8: Update `handle_list_experiments` in `src/ml_mcp/mcp/tools/experiments.py` to validate `project_id` existence.
- [ ] Task 9: Register `create_project` and `list_projects` tools in `src/ml_mcp/server/app.py`, add default project seeding in `app_lifespan`, and sanitize database exceptions in `_execute_secured`.

### Checkpoint: FastMCP Server Layer
- [ ] `create_server()` registers all 23 tools.
- [ ] Startup seeds `default-project` for `default-tenant`.
- [ ] Constraint violations return sanitized domain errors without SQL leakage.

### Phase 4: Downstream Tool Verification & Contract Tests
- [ ] Task 10: Update contract tests in `tests/contract/test_mcp_tools.py` for 23 tools, project management, and format verification.
- [ ] Task 11: Create comprehensive integration test `tests/integration/test_test_report_remediation.py` testing all previously failing/blocked write paths and downstream tools end-to-end against live PostgreSQL.

### Checkpoint: Complete Verification
- [ ] All contract and integration tests pass (100% green).
- [ ] Ruff linting passes with 0 errors.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Adding 2 new tools breaks tests asserting exact tool count (21) | High | Update `test_tool_catalog_contract` assertion from 21 to 23 and include `create_project` & `list_projects`. |
| Auto-seeding default project fails if tenant does not exist | Med | In `ensure_default_project`, check and ensure `default-tenant` exists first in the database. |
| Existing migrations might require schema changes | Low | `ProjectOrm` already exists in `models.py` and Alembic migrations already created `projects` table; no migration changes needed. |
