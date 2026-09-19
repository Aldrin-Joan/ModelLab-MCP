# Implementation Plan: Agentic ML MCP Server (ModelLab)

## Overview
A production-grade, secure, reproducible machine learning experimentation control plane exposed via the Model Context Protocol (MCP `2026-07-28` standard and FastMCP 4), executing on Python 3.13 within the `ML_LLM` conda environment.

## Architecture Decisions & Rationale
1. **Control Plane / Execution Plane Separation**: FastMCP handles tool routing, schema validation, and authorization, but never directly imports or trains ML models on the server event loop. ML workers execute asynchronously in containerized or process-isolated boundaries.
2. **Durable Outbox Pattern**: Experiments submitted via FastMCP are written transactionally with an outbox event in PostgreSQL before being dispatched to the Redis queue, preventing lost submissions during transient failures.
3. **Pydantic 2 & JSON Schema 2020-12**: Strict type validation across all MCP inputs and outputs. Models and datasets are registered, versioned, and addressed by content hash.
4. **Parquet / Arrow Internal Representation**: Analytical datasets and predictions are stored in Apache Parquet/Arrow format for compression, performance, and typed streaming.
5. **Multi-Transport Support**: Native STDIO (clean stdout for JSON-RPC; stderr for structured logs) and Streamable HTTP (OAuth 2.1 / OIDC Bearer JWT, stateless requests, health probes at `/health/live` and `/health/ready`).

## Task List

### Phase 1: Project Scaffolding, Tooling & Configuration
- [ ] Task 1.1: Project Baseline & Dependency Management (`pyproject.toml`, conda `ML_LLM`, tooling configs)
- [ ] Task 1.2: Centralized Application Configuration & Settings (`settings.py`, Pydantic Settings)
- [ ] Task 1.3: Telemetry, Structured Logging & Local Infrastructure Setup (`logging.py`, `otel.py`, `docker-compose.yml`)

### Checkpoint 1: Scaffolding & Infrastructure
- [ ] Dependencies verified in `ML_LLM` conda env
- [ ] Structured logging outputs strictly to stderr
- [ ] Local persistence services operational via Docker Compose

### Phase 2: Domain Modeling, Policies & Error Handling
- [ ] Task 2.1: Domain Errors & Stable Error Codes (`codes.py`, sanitized exceptions)
- [ ] Task 2.2: Value Objects & Experiment Specifications (`ExperimentSpec`, `TaskType`, `ModelFamily`, schemas)
- [ ] Task 2.3: Security Policies, RBAC Matrix & Tool Classification (`rbac.py`, `tool_policy.py`, `tenant_isolation.py`)

### Checkpoint 2: Domain Layer
- [ ] Domain errors sanitized and standardized
- [ ] Value objects enforce business invariants
- [ ] RBAC and tenant isolation policy test suite passes

### Phase 3: Database & Persistence Infrastructure
- [ ] Task 3.1: Async SQLAlchemy 2 ORM Models (Tenants, Models, Datasets, Experiments, Metrics, Artifacts, Outbox, Audit)
- [ ] Task 3.2: Database Engine, Session Factory & Alembic Migrations (`session.py`, `alembic/`)
- [ ] Task 3.3: Repository Implementations (Model, Dataset, Experiment, Metric, Artifact, Outbox, Audit repositories)

### Checkpoint 3: Persistence Layer
- [ ] Database migrations execute up and down cleanly
- [ ] Repositories pass integration tests against PostgreSQL
- [ ] Outbox pattern verified within database transactions

### Phase 4: Object Storage & Data Processing Engine
- [ ] Task 4.1: S3-Compatible Storage Adapter & Presigned URLs (`s3.py`, MinIO integration)
- [ ] Task 4.2: Dataset Validation, Schema Extraction & Ingestion (CSV, Parquet, JSONL validation & SHA-256)
- [ ] Task 4.3: Model Catalog Application Service (approved model registry & hyperparameter validation)

### Checkpoint 4: Storage & Catalog Services
- [ ] S3 uploads, downloads, and presigned URLs validated
- [ ] Ingestion validates CSV/Parquet/JSONL datasets
- [ ] Model catalog enforces approval constraints

### Phase 5: Redis Infrastructure, Rate Limiting & Outbox Queue
- [ ] Task 5.1: Redis Client & Sliding-Window Rate Limiter (`client.py`, `rate_limiter.py`)
- [ ] Task 5.2: Durable Outbox Processor & Task Queue (`task_queue.py`, `outbox_processor.py`)

### Checkpoint 5: Rate Limiting & Queue Pipeline
- [ ] Sliding-window rate limiter prevents abuse across all tool classes
- [ ] Outbox processor guarantees reliable event publication from Postgres to Redis

### Phase 6: Tabular ML Execution Worker Engine
- [ ] Task 6.1: ML Feature Preprocessing & Split Pipeline (leak-free imputers, encoders, scalers, cross-validation splits)
- [ ] Task 6.2: Model Trainers & Evaluation Engine (Logistic Regression, Random Forest, XGBoost, LightGBM, CatBoost, Linear SVM, MLP + metric suite)
- [ ] Task 6.3: Worker Orchestrator & Execution Isolation Boundary (runner loop, timeouts, memory bounds, artifact persistence)

### Checkpoint 6: ML Worker Execution
- [ ] Preprocessing guarantees zero data leakage
- [ ] All 7 tabular model trainers execute and compute metrics
- [ ] Worker runner safely manages timeouts and uploads artifacts

### Phase 7: Structured Analysis Engine
- [ ] Task 7.1: Statistical Analysis, Overfitting & Leakage Detection (overfitting gap, leakage indicators, error analysis)

### Checkpoint 7: Analysis Engine
- [ ] Read-only analysis delivers comprehensive diagnostic findings
- [ ] Recommendations and statistical observations formatted cleanly

### Phase 8: FastMCP Protocol Adapter, Transports & Security Pipeline
- [ ] Task 8.1: Authentication & JWT Validation Module (OAuth 2.1 / OIDC Bearer JWT validation)
- [ ] Task 8.2: FastMCP Schemas & Tool Implementations (Discovery, Dataset, Experiment, Results, Analysis tools)
- [ ] Task 8.3: FastMCP Resources, Prompts & Server Factory (`resources.py`, `prompts.py`, `app.py`)
- [ ] Task 8.4: Transports (STDIO & Streamable HTTP) & Health Endpoints (`stdio.py`, `http.py`, `/health/*`)

### Checkpoint 8: FastMCP Server & Transports
- [ ] All 18 MCP tools operational with schema validation
- [ ] STDIO transport preserves pure JSON-RPC stdout
- [ ] Streamable HTTP transport enforces auth and responds to health endpoints

### Phase 9: Comprehensive Security, Contract & E2E Verification
- [ ] Task 9.1: Security Test Matrix Implementation (JWT attacks, scope escalation, tenant isolation, path traversal)
- [ ] Task 9.2: End-to-End Experimentation Lifecycle Test (register dataset -> experiment -> worker -> metrics -> analysis)

### Checkpoint 9: Security & E2E Verification
- [ ] Security test matrix passes all attack scenarios
- [ ] E2E lifecycle test passes with real ML training and analysis

### Phase 10: Containerization, CI/CD & Deployment Artifacts
- [ ] Task 10.1: Multi-Stage Production Dockerfiles (`ml-mcp-api` & `ml-worker-tabular-cpu`)
- [ ] Task 10.2: GitHub Actions CI Pipeline & Operational Documentation (`.github/workflows/ci.yml`, `Docs/Operational-Guide.md`)

### Checkpoint 10: Production Readiness Complete
- [ ] Docker images build clean, non-root, hardened
- [ ] CI pipeline validates formatting, linting, typing, tests

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| ML Worker Resource Exhaustion | High | Process quotas, wall-clock timeouts, isolated execution boundary, and task cancellation handling. |
| Data Leakage during Preprocessing | High | Strict leak-free pipeline where transforms are fit exclusively on train splits; automated leakage checks in analysis engine. |
| STDIO Stream Contamination | High | Strict logging configuration directing all output, traces, and diagnostics to `sys.stderr`. |
| Cross-Tenant Data Access | Critical | Repository-level tenant scoping, JWT claim binding, and automated security test matrix. |

## Open Questions
- None currently blocking; all architectural specifications in `Docs/Tech-Stack.md` and `Docs/Architecture.md` are aligned.
