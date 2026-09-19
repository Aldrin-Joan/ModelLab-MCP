# Task List: Agentic ML MCP Server (ModelLab)

<!-- Tracking file for agent tasks according to planning-and-task-breakdown skill -->

## Phase 1: Project Scaffolding, Tooling & Configuration
- [x] **Task 1.1**: Project Baseline & Dependency Management
  - Files: `pyproject.toml`, `README.md`, `.gitignore`
  - Verification: `conda run -n ML_LLM python -c "import fastmcp, pydantic, sqlalchemy; print('OK')"`
- [x] **Task 1.2**: Centralized Application Configuration & Settings
  - Files: `src/ml_mcp/config/__init__.py`, `src/ml_mcp/config/settings.py`, `tests/unit/test_settings.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_settings.py`
- [x] **Task 1.3**: Telemetry, Structured Logging & Local Infrastructure Setup
  - Files: `src/ml_mcp/infrastructure/telemetry/logging.py`, `src/ml_mcp/infrastructure/telemetry/otel.py`, `docker-compose.yml`, `tests/unit/test_logging.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_logging.py`

### Checkpoint 1: Scaffolding & Infrastructure
- [x] All Phase 1 tests pass
- [x] Docker services launch cleanly
- [x] Stderr logging verified

## Phase 2: Domain Modeling, Policies & Error Handling
- [x] **Task 2.1**: Domain Errors & Stable Error Codes
  - Files: `src/ml_mcp/domain/errors/base.py`, `src/ml_mcp/domain/errors/codes.py`, `tests/unit/test_errors.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_errors.py`
- [x] **Task 2.2**: Value Objects & Experiment Specifications
  - Files: `src/ml_mcp/domain/value_objects/experiment.py`, `src/ml_mcp/domain/value_objects/dataset.py`, `src/ml_mcp/domain/value_objects/model.py`, `tests/unit/test_value_objects.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_value_objects.py`
- [x] **Task 2.3**: Security Policies, RBAC Matrix & Tool Classification
  - Files: `src/ml_mcp/domain/policies/rbac.py`, `src/ml_mcp/domain/policies/tool_policy.py`, `src/ml_mcp/domain/policies/tenant_isolation.py`, `tests/unit/test_policies.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_policies.py`

### Checkpoint 2: Domain Layer
- [x] All domain value objects enforce business rules
- [x] Policy engine passes 100% of RBAC and tenant tests

## Phase 3: Database & Persistence Infrastructure
- [x] **Task 3.1**: Async SQLAlchemy 2 ORM Models
  - Files: `src/ml_mcp/infrastructure/postgres/base.py`, `src/ml_mcp/infrastructure/postgres/models.py`, `tests/unit/test_orm_models.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_orm_models.py`
- [x] **Task 3.2**: Database Engine, Session Factory & Alembic Migrations
  - Files: `src/ml_mcp/infrastructure/postgres/session.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`
  - Verification: `conda run -n ML_LLM alembic upgrade head`
- [x] **Task 3.3**: Repository Implementations
  - Files: `src/ml_mcp/infrastructure/postgres/repositories/*.py`, `tests/integration/test_repositories.py`
  - Verification: `conda run -n ML_LLM pytest tests/integration/test_repositories.py`

### Checkpoint 3: Persistence Layer
- [x] Alembic migrations run cleanly up/down
- [x] Repositories pass integration tests with PostgreSQL

## Phase 4: Object Storage & Data Processing Engine
- [x] **Task 4.1**: S3-Compatible Storage Adapter & Presigned URLs
  - Files: `src/ml_mcp/infrastructure/object_storage/s3.py`, `tests/unit/test_object_storage.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_object_storage.py`
- [x] **Task 4.2**: Dataset Validation, Schema Extraction & Ingestion
  - Files: `src/ml_mcp/application/datasets/service.py`, `src/ml_mcp/application/datasets/validator.py`, `tests/unit/test_dataset_service.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_dataset_service.py`
- [x] **Task 4.3**: Model Catalog Application Service
  - Files: `src/ml_mcp/application/models/service.py`, `src/ml_mcp/application/models/catalog_seed.py`, `tests/unit/test_model_service.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_model_service.py`

### Checkpoint 4: Storage & Catalog
- [x] S3 storage and presigned URLs verified
- [x] Dataset validation rejects unsafe/malformed files
- [x] Model catalog enforces approval constraints

## Phase 5: Redis Infrastructure, Rate Limiting & Outbox Queue
- [x] **Task 5.1**: Redis Client & Sliding-Window Rate Limiter
  - Files: `src/ml_mcp/infrastructure/redis/client.py`, `src/ml_mcp/infrastructure/redis/rate_limiter.py`, `tests/integration/test_rate_limiter.py`
  - Verification: `conda run -n ML_LLM pytest tests/integration/test_rate_limiter.py`
- [x] **Task 5.2**: Durable Outbox Processor & Task Queue
  - Files: `src/ml_mcp/infrastructure/queue/task_queue.py`, `src/ml_mcp/infrastructure/queue/outbox_processor.py`, `tests/integration/test_outbox_queue.py`
  - Verification: `conda run -n ML_LLM pytest tests/integration/test_outbox_queue.py`

### Checkpoint 5: Rate Limiting & Outbox
- [x] Rate limiter blocks traffic over limits
- [x] Outbox processor ensures reliable message transfer to queue

## Phase 6: Tabular ML Execution Worker Engine
- [x] **Task 6.1**: ML Feature Preprocessing & Split Pipeline
  - Files: `src/ml_mcp/workers/preprocessing.py`, `tests/unit/test_preprocessing.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_preprocessing.py`
- [x] **Task 6.2**: Model Trainers & Evaluation Engine
  - Files: `src/ml_mcp/workers/trainers/*.py`, `src/ml_mcp/workers/metrics.py`, `tests/unit/test_trainers.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_trainers.py`
- [x] **Task 6.3**: Worker Orchestrator & Execution Isolation Boundary
  - Files: `src/ml_mcp/workers/runner.py`, `src/ml_mcp/workers/sandbox.py`, `tests/integration/test_worker_runner.py`
  - Verification: `conda run -n ML_LLM pytest tests/integration/test_worker_runner.py`

### Checkpoint 6: ML Worker Engine
- [x] All 7 tabular models train and output metrics
- [x] Zero data leakage during preprocessing
- [x] Worker runner catches timeouts and updates status

## Phase 7: Structured Analysis Engine
- [x] **Task 7.1**: Statistical Analysis, Overfitting & Leakage Detection
  - Files: `src/ml_mcp/application/analysis/service.py`, `src/ml_mcp/application/analysis/diagnostics.py`, `tests/unit/test_analysis_service.py`
  - Verification: `conda run -n ML_LLM pytest tests/unit/test_analysis_service.py`

### Checkpoint 7: Analysis Engine
- [x] Diagnostic engine correctly flags overfitting and leakage
- [x] Outputs formatted strictly to specification

## Phase 8: FastMCP Protocol Adapter, Transports & Security Pipeline
- [x] **Task 8.1**: Authentication & JWT Validation Module
  - Files: `src/ml_mcp/server/auth.py`, `tests/unit/test_auth.py`
  - Verification: `pytest tests/unit/test_auth.py`
- [x] **Task 8.2**: FastMCP Schemas & Tool Implementations (all 21 tools)
  - Files: `src/ml_mcp/mcp/schemas/tools.py`, `src/ml_mcp/mcp/tools/*.py`, `tests/contract/test_mcp_tools.py`
  - Verification: `pytest tests/contract/test_mcp_tools.py`
- [x] **Task 8.3**: FastMCP Resources, Prompts & Server Factory
  - Files: `src/ml_mcp/mcp/resources.py`, `src/ml_mcp/mcp/prompts.py`, `src/ml_mcp/server/app.py`, `tests/contract/test_mcp_tools.py`
  - Verification: `pytest tests/contract/test_mcp_tools.py`
- [x] **Task 8.4**: Transports (STDIO & Streamable HTTP) & Health Endpoints
  - Files: `src/ml_mcp/server/stdio.py`, `src/ml_mcp/server/http.py`, `src/ml_mcp/server/middleware.py`, `tests/unit/test_transports.py`
  - Verification: `pytest tests/unit/test_transports.py`

### Checkpoint 8: FastMCP Transports
- [x] STDIO transport leaves stdout uncontaminated
- [x] Streamable HTTP authenticates and serves health probes

## Phase 9: Comprehensive Security, Contract & E2E Verification
- [x] **Task 9.1**: Security Test Matrix Implementation
  - Files: `tests/security/test_security_matrix.py`
  - Verification: `pytest tests/security/test_security_matrix.py`
- [x] **Task 9.2**: End-to-End Experimentation Lifecycle Test
  - Files: `tests/e2e/test_full_lifecycle.py`
  - Verification: `pytest tests/e2e/test_full_lifecycle.py`

### Checkpoint 9: Security & Verification
- [x] All 15+ security test vectors pass
- [x] Complete E2E experiment lifecycle passes green

## Phase 10: Containerization, CI/CD & Deployment Artifacts
- [x] **Task 10.1**: Multi-Stage Production Dockerfiles
  - Files: `Dockerfile`, `.gitignore`
  - Verification: Multi-stage targets `ml-mcp-api` and `ml-worker-tabular-cpu`
- [x] **Task 10.2**: GitHub Actions CI Pipeline & Documentation
  - Files: `.github/workflows/ci.yml`, `Docs/Operational-Guide.md`
  - Verification: Ruff linting, test suite, and operational runbooks

### Checkpoint 10: Production Readiness Complete
- [x] Production Docker containers defined and validated
- [x] CI pipeline ready for deployment
- [x] 75 of 75 tests passing green across entire repo
