# Tech-Stack.md

# Agentic ML MCP Server --- Production Technology Stack

## 1. Stack Decision

  -----------------------------------------------------------------------
  Layer                   Technology              Decision
  ----------------------- ----------------------- -----------------------
  Language                Python 3.13             Production baseline

  MCP framework           FastMCP 4.x             Primary MCP
                                                  implementation

  MCP protocol            2026-07-28              Current production
                                                  baseline

  Local transport         STDIO                   Required

  Remote transport        Streamable HTTP         Required

  Web server              FastMCP HTTP runtime /  Required
                          ASGI deployment         

  Reverse proxy           Envoy or cloud-native   Production edge
                          load balancer           

  TLS                     Managed TLS / TLS 1.3   Required
                          preferred               

  Auth                    OAuth 2.1 + OIDC        Remote authentication

  Token format            JWT                     Access-token validation

  Validation              Pydantic 2.x            Strict schemas

  ORM                     SQLAlchemy 2.x          PostgreSQL access

  Database                PostgreSQL 16+          System of record

  Migrations              Alembic                 Schema migrations

  Cache / queue           Redis or Valkey         Rate limiting + task
                                                  infrastructure

  Object storage          S3-compatible           Dataset/artifact
                                                  storage

  Serialization           JSON + JSON Schema      MCP/application
                          2020-12                 contracts

  Async runtime           asyncio                 Non-blocking server

  HTTP client             httpx                   Controlled outbound
                                                  HTTP

  ML execution            Isolated containers     Worker boundary

  CPU ML                  scikit-learn, XGBoost,  Initial model ecosystem
                          LightGBM, CatBoost      

  Data processing         pandas + PyArrow        Tabular datasets

  Experiment tracking     PostgreSQL + object     First-party source of
                          storage                 truth

  Telemetry               OpenTelemetry           Traces/metrics/log
                                                  correlation

  Metrics                 Prometheus-compatible   Operational metrics

  Logs                    JSON structured logs    Centralized logging

  Testing                 pytest + pytest-asyncio Required

  Type checking           ty                      Required

  Lint/format             Ruff                    Required

  Package manager         uv                      Required

  Container               OCI/Docker              Required

  CI                      GitHub Actions          Required

  Secrets                 Cloud secret manager /  Required
                          Vault                   

  IaC                     Terraform               Production
                                                  infrastructure

  Container scanning      Trivy                   CI gate

  Dependency scanning     pip-audit /             CI gate
                          OSV-compatible scanner  
  -----------------------------------------------------------------------

## 2. Why Python

Python is the correct primary language because the project eventually
needs to interact directly with:

``` text
scikit-learn
XGBoost
LightGBM
CatBoost
PyTorch
TensorFlow
PyArrow
pandas
NumPy
```

It also provides a mature async ecosystem and strong FastMCP support.

The MCP control plane should remain lightweight even though workers can
use larger ML runtimes.

## 3. Python Version

Use:

``` text
Python 3.13
```

Reason:

-   modern typing
-   stable async runtime
-   broad ML package compatibility
-   mature production ecosystem
-   avoids unnecessarily coupling the MCP control plane to bleeding-edge
    interpreter support

Python 3.14 can be introduced after the full ML worker matrix is
certified against it.

## 4. MCP Framework

Use:

``` text
fastmcp==4.x.y
```

with an exact version pinned in `uv.lock`.

FastMCP 4 is currently GA and supports MCP 2026-07-28. It also supports
compatibility with older MCP clients. citeturn1search0

FastMCP is preferred over implementing the MCP protocol directly because
it provides:

``` text
tools
resources
prompts
authentication integration
transport handling
testing client
background task integration
typed outputs
```

FastMCP's documentation explicitly recommends exact version pinning for
production because the MCP ecosystem evolves rapidly.
citeturn2search1

## 5. MCP Transports

### STDIO

Use FastMCP's STDIO transport for local clients.

Conceptually:

``` python
mcp.run(transport="stdio")
```

STDIO process contract:

``` text
stdin  -> MCP messages
stdout -> MCP messages
stderr -> diagnostics
```

Never write logs to stdout.

### HTTP

Use Streamable HTTP.

Development:

``` bash
fastmcp run src/ml_mcp/server/app.py:mcp --transport http --port 8000
```

FastMCP documents the same HTTP deployment pattern for protected
servers. citeturn2search2turn2search4

Production:

``` text
HTTPS edge
    ↓
FastMCP HTTP application
```

Do not build new production functionality around the deprecated legacy
HTTP+SSE transport. MCP's 2026-07-28 release identifies Streamable HTTP
as the modern HTTP model and the older HTTP+SSE transport as deprecated.
citeturn0search0

## 6. FastMCP Server Structure

Use one shared application factory:

``` text
create_server()
       |
       +-- register tools
       +-- register resources
       +-- register prompts
       +-- register middleware
       +-- configure auth
       +-- configure lifespan
```

Then expose:

``` text
STDIO entrypoint
HTTP entrypoint
```

Both must use the same application/domain services.

``` mermaid
flowchart LR
    STDIO["STDIO Entrypoint"]
    HTTP["HTTP Entrypoint"]

    STDIO --> FACTORY["create_server()"]
    HTTP --> FACTORY

    FACTORY --> TOOLS["MCP Tools"]
    FACTORY --> RES["Resources"]
    FACTORY --> SERVICES["Application Services"]
```

This prevents the STDIO and HTTP implementations from drifting apart.

## 7. Pydantic

Use Pydantic 2.x for:

``` text
MCP tool inputs
MCP outputs
database DTOs
experiment specifications
model metadata
dataset metadata
API configuration
security claims
```

Use strict validation wherever practical.

Example conceptual schema:

``` text
ExperimentSpec
├── dataset_version_id
├── model_version_id
├── task_type
├── split_strategy
├── evaluation
├── hyperparameters
├── random_seed
└── resource_policy
```

Never deserialize arbitrary JSON directly into execution commands.

## 8. PostgreSQL

Use PostgreSQL 16 or newer.

Primary tables:

``` text
tenants
principals
projects

models
model_versions

datasets
dataset_versions

experiments
experiment_runs

metrics
analysis_runs

artifacts
outbox_events
audit_events
```

Important indexes:

``` text
(tenant_id, created_at)
(project_id, created_at)
(model_id, version)
(dataset_id, version)
(experiment_id)
(experiment_id, metric_name)
(status, created_at)
```

Use UUIDv7 or another time-sortable identifier strategy for externally
visible IDs.

## 9. SQLAlchemy

Use:

``` text
SQLAlchemy 2.x
```

with async PostgreSQL access.

Use:

``` text
asyncpg
```

for the PostgreSQL driver.

Do not expose SQLAlchemy models directly through MCP responses. Convert
domain/application objects into explicit response schemas.

## 10. Alembic

All schema changes use Alembic migrations.

Production migration process:

``` text
build
 ↓
migration validation
 ↓
backup verification
 ↓
migration
 ↓
application rollout
 ↓
health verification
```

Destructive migrations require an explicit expand/contract migration
sequence.

## 11. Redis / Valkey

Use Redis or Valkey for:

``` text
rate limiting
short-lived cache
task queue
distributed locks where unavoidable
```

Do not store authoritative experiment state only in Redis.

For production FastMCP background tasks, a persistent Redis/Valkey
backend is preferable to the in-memory backend because the latter loses
pending tasks on restart and cannot scale horizontally.
citeturn2search5

## 12. Object Storage

Use an S3-compatible object store.

Examples:

``` text
AWS S3
Azure Blob Storage through S3-compatible abstraction where available
MinIO for controlled self-hosted environments
```

Recommended object hierarchy:

``` text
tenants/{tenant_id}/
    datasets/{dataset_id}/{version}/
    experiments/{experiment_id}/
        predictions/
        metrics/
        reports/
        logs/
    models/{model_id}/{version}/
```

Objects are immutable after finalization.

## 13. Data Formats

Dataset ingestion:

``` text
CSV
Parquet
JSONL
```

Internal analytical representation:

``` text
Apache Arrow / Parquet
```

Why Parquet:

``` text
columnar
compressed
typed
efficient
streamable
Python ecosystem support
```

Avoid making CSV the internal canonical format.

## 14. Model Registry

The initial registry should not be a generic "execute anything"
registry.

It is a controlled catalog:

``` text
model
    |
    +-- metadata
    +-- version
    +-- artifact digest
    +-- container image digest
    +-- schema
    +-- supported task
    +-- resource profile
    +-- approval status
```

Initial model families:

``` text
Logistic Regression
Random Forest
XGBoost
LightGBM
CatBoost
Linear SVM
MLP
```

The first release should prioritize tabular ML because it provides a
manageable, reproducible execution contract.

## 15. Dataset Registry

Dataset registry contains:

``` text
dataset_id
version
schema
row_count
column_count
feature_types
target_definition
content_hash
object_location
license
classification
validation_status
created_by
```

Dataset metadata must never be treated as trusted merely because it came
from a registered client.

## 16. ML Worker Runtime

The MCP API environment should not install every ML framework.

Separate images:

``` text
ml-mcp-api
ml-worker-tabular-cpu
ml-worker-tabular-gpu
ml-worker-pytorch
```

This keeps the control plane small.

### API image

Contains:

``` text
FastMCP
Pydantic
SQLAlchemy
asyncpg
Redis client
S3 client
OpenTelemetry
```

### Tabular CPU image

Contains:

``` text
NumPy
pandas
PyArrow
scikit-learn
XGBoost
LightGBM
CatBoost
```

### GPU images

Added only after GPU worker contracts are defined and tested.

## 17. Worker Isolation

Each execution uses an isolated container.

Security baseline:

``` text
non-root
read-only root filesystem
no privileged mode
no Docker socket
no host network
no host PID namespace
no host filesystem mounts
CPU quota
memory quota
PID quota
wall-clock timeout
temporary workspace
restricted network
```

The worker receives only:

``` text
experiment specification
temporary object-store credentials
required dataset objects
approved model artifact
```

## 18. Networking

Production:

``` text
Internet
   ↓
WAF / Load Balancer
   ↓
MCP API
   ↓
private services
```

The API can reach:

``` text
PostgreSQL
Redis/Valkey
Object Storage
OpenTelemetry Collector
```

Workers can reach only:

``` text
Object Storage
Telemetry endpoint
Required internal control endpoint
```

Default worker egress:

``` text
DENY
```

This prevents a model from silently making arbitrary internet requests.

## 19. Authentication

Remote authentication:

``` text
OAuth 2.1 / OIDC
```

FastMCP supports OAuth integrations and bearer-token authentication for
HTTP transports. citeturn2search10turn2search14

For production, use an external identity provider rather than
implementing password authentication in the MCP server.

The server validates:

``` text
iss
aud
exp
nbf
sub
scope
signature
algorithm
```

Do not accept:

``` text
none
HS256 when the configured issuer uses asymmetric signing
unexpected algorithms
expired tokens
tokens from another issuer
```

## 20. Authorization

Use:

``` text
RBAC
+
project/tenant resource authorization
+
scope checks
```

Example scopes:

``` text
ml:models:read
ml:datasets:read
ml:datasets:write
ml:experiments:read
ml:experiments:create
ml:experiments:cancel
ml:analysis:create
ml:artifacts:read
ml:admin
```

## 21. HTTP Security

At the edge:

``` text
TLS
HSTS
request-size limits
header-size limits
HTTP method allowlist
rate limiting
WAF rules
```

Application:

``` text
CORS only where genuinely required
strict content types
MCP header validation
authorization on every protected operation
```

Do not expose administrative endpoints through the MCP endpoint.

## 22. HTTP Client

Use:

``` text
httpx.AsyncClient
```

for outbound HTTP.

Every request has:

``` text
connect timeout
read timeout
write timeout
overall timeout
retry budget
```

Retries are allowed only for transient operations.

Never blindly retry:

``` text
POST mutations
model execution submission
authorization operations
```

unless the operation is explicitly idempotent.

## 23. Configuration

Use Pydantic Settings.

Configuration sources:

``` text
environment variables
secret manager
deployment configuration
```

Never hardcode:

``` text
passwords
API keys
JWT signing keys
database credentials
cloud credentials
```

Example configuration groups:

``` text
APP_
MCP_
AUTH_
DATABASE_
REDIS_
OBJECT_STORE_
WORKER_
OTEL_
RATE_LIMIT_
SECURITY_
```

## 24. Dependency Management

Use:

``` text
uv
pyproject.toml
uv.lock
```

Pin exact versions in the lockfile.

CI must reject:

``` text
unlocked production dependencies
known critical vulnerabilities
unexpected dependency drift
```

FastMCP's release guidance specifically recommends exact production
version pinning. citeturn2search1

## 25. Code Quality

Required:

``` text
Ruff
ty
pytest
pytest-asyncio
pre-commit
```

CI order:

``` text
format check
 ↓
lint
 ↓
type check
 ↓
unit tests
 ↓
integration tests
 ↓
security tests
 ↓
MCP contract tests
 ↓
build
 ↓
container scan
```

FastMCP itself uses Ruff, ty and pytest-oriented testing practices,
making this toolchain consistent with the framework ecosystem.
citeturn2search13turn2search17

## 26. Testing Strategy

### Unit

Test:

``` text
domain rules
validation
authorization
rate limiting
experiment state transitions
artifact policies
```

### Integration

Test:

``` text
PostgreSQL
Redis
object storage
authentication
queue
```

### MCP contract

Test:

``` text
tools/list
resources/list
tools/call
resource reads
schema validation
error mapping
```

### Transport

Test:

``` text
STDIO
Streamable HTTP
authenticated HTTP
expired authentication
invalid headers
```

### Security

Test:

``` text
tenant isolation
scope escalation
path traversal
oversized payload
artifact bypass
JWT attacks
rate-limit bypass
secret leakage
```

### End-to-end

Test:

``` text
dataset registration
 ↓
validation
 ↓
experiment creation
 ↓
queue
 ↓
worker
 ↓
artifact creation
 ↓
result retrieval
 ↓
analysis
```

FastMCP provides a client-oriented testing approach that can be combined
with pytest and pytest-asyncio. citeturn2search17

## 27. Observability Stack

Use:

``` text
OpenTelemetry SDK
        ↓
OpenTelemetry Collector
        ├── Prometheus
        ├── Grafana
        └── Tempo / compatible trace backend
```

Structured application logs can be shipped to the organization's
centralized log platform.

Every request gets:

``` text
request_id
trace_id
principal_id
tenant_id
```

where permitted by privacy policy.

## 28. Security Scanning

CI:

``` text
Ruff
ty
pip-audit / OSV
Trivy filesystem scan
Trivy container scan
secret scanning
SBOM generation
```

Production images should be rebuilt regularly even without application
changes to consume base-image security updates.

## 29. Container Build

Use multi-stage builds.

``` dockerfile
builder
   ↓
install locked dependencies
   ↓
runtime
   ↓
copy application only
```

Runtime container:

``` text
non-root
minimal base
read-only filesystem
no compiler toolchain
no package manager
```

## 30. Infrastructure

Terraform manages:

``` text
network
load balancer
TLS
database
Redis/Valkey
object storage
container registry
Kubernetes/container platform
identity configuration
secrets references
monitoring
```

Do not manage runtime experiment state through Terraform.

## 31. Deployment Strategy

Use:

``` text
dev
staging
production
```

Promotion:

``` text
commit
 ↓
CI
 ↓
security gates
 ↓
container image
 ↓
staging deployment
 ↓
integration/e2e
 ↓
approval
 ↓
production rollout
```

Production rollout should support:

``` text
rolling deployment
health checks
automatic rollback
database expand/contract migrations
```

## 32. Health Endpoints

The HTTP application exposes operational health outside the MCP protocol
endpoint:

``` text
/health/live
/health/ready
```

Liveness:

``` text
process is alive
```

Readiness checks:

``` text
database reachable
required configuration loaded
required dependencies initialized
```

Do not make readiness dependent on optional external services.

## 33. Resource Limits

API:

``` text
bounded request body
bounded response size
bounded concurrent requests
bounded outbound connections
```

Experiment:

``` text
max runtime
max CPU
max memory
max artifact size
max prediction rows
max concurrent experiments
```

Dataset:

``` text
max upload size
max rows after parsing
max columns
max string length
```

These limits are configured per deployment and optionally per tenant.

## 34. MCP Tool Output Design

Tool responses should be compact.

Bad:

``` text
return entire 5 GB prediction file
```

Good:

``` json
{
  "experiment_id": "...",
  "status": "SUCCEEDED",
  "metrics": {
    "pr_auc": 0.8124,
    "roc_auc": 0.9711,
    "f1": 0.7312
  },
  "artifacts": [
    {
      "artifact_id": "...",
      "type": "predictions",
      "size_bytes": 18429321
    }
  ]
}
```

Large artifacts are retrieved separately.

## 35. API/MCP Versioning

Version application schemas independently from MCP protocol versions.

Example:

``` text
MCP protocol:
2026-07-28

Application schema:
experiment.v1
dataset.v1
model.v1
analysis.v1
```

Never encode application versioning into MCP tool names unless a
breaking compatibility boundary genuinely requires it.

## 36. Error Model

Use stable machine-readable error codes.

Examples:

``` text
AUTHENTICATION_REQUIRED
AUTHORIZATION_DENIED
RESOURCE_NOT_FOUND
RESOURCE_VERSION_REVOKED
INVALID_EXPERIMENT
DATASET_VALIDATION_FAILED
MODEL_NOT_APPROVED
EXPERIMENT_ALREADY_EXISTS
EXPERIMENT_NOT_CANCELLABLE
TASK_UNAVAILABLE
ARTIFACT_ACCESS_DENIED
RESOURCE_LIMIT_EXCEEDED
DEPENDENCY_UNAVAILABLE
```

Errors must not leak:

``` text
database connection strings
filesystem paths
stack traces
tokens
secrets
internal hostnames
```

Detailed diagnostics remain in protected logs.

## 37. Performance Targets

Initial API targets:

``` text
catalog read p50 < 50 ms
catalog read p95 < 150 ms
authorization p95 < 20 ms
experiment creation p95 < 200 ms excluding queue latency
artifact metadata p95 < 100 ms
```

ML execution latency is measured separately because model training time
is workload-dependent.

The API must never synchronously wait for training.

## 38. Concurrency

Use asynchronous I/O for:

``` text
PostgreSQL
Redis
object storage
HTTP
MCP request handling
```

CPU-heavy work does not execute on the MCP event loop.

Use worker processes/containers for:

``` text
training
inference
dataset processing
large artifact generation
```

## 39. Initial Release Scope

The first production release should implement:

``` text
STDIO transport
Streamable HTTP
authentication
authorization
model catalog
dataset catalog
dataset validation
experiment creation
experiment state
durable queue
artifact metadata
metrics retrieval
comparison
structured analysis
audit logging
OpenTelemetry
rate limiting
tenant isolation
security tests
```

The initial model scope is tabular ML.

This keeps the first implementation production-grade instead of
attempting every ML modality simultaneously.

## 40. Explicitly Out of Scope for the First Release

The following are not part of the first release:

``` text
arbitrary Python execution
arbitrary shell execution
automatic package installation
automatic model downloading from arbitrary URLs
untrusted model execution
public dataset scraping
automatic internet access from workers
LLM-generated training code execution
fully autonomous hyperparameter search
multi-modal model execution
```

They can be introduced later only through explicit security and
execution contracts.

## 41. Recommended Production Topology

``` mermaid
flowchart TB
    USER["AI Client / Agent"]

    subgraph EDGE["Public Edge"]
        DNS["DNS"]
        WAF["WAF / Load Balancer"]
        TLS["TLS"]
    end

    subgraph API["Private Application Subnet"]
        A1["ML-MCP API 1"]
        A2["ML-MCP API 2"]
        A3["ML-MCP API N"]
    end

    subgraph STATE["Private State Layer"]
        PG["PostgreSQL"]
        REDIS["Redis / Valkey"]
        S3["Object Storage"]
    end

    subgraph WORKERS["Isolated Worker Subnet"]
        CPU["CPU ML Workers"]
        GPU["GPU ML Workers"]
        TASK["Task / Outbox Workers"]
    end

    subgraph OBS["Observability"]
        OTEL["OpenTelemetry Collector"]
        PROM["Prometheus"]
        GRAF["Grafana"]
        TRACE["Trace Backend"]
    end

    USER --> DNS --> WAF --> TLS
    TLS --> A1
    TLS --> A2
    TLS --> A3

    A1 --> PG
    A2 --> PG
    A3 --> PG

    A1 --> REDIS
    A2 --> REDIS
    A3 --> REDIS

    A1 --> S3
    A2 --> S3
    A3 --> S3

    REDIS --> TASK
    TASK --> CPU
    TASK --> GPU

    CPU --> S3
    GPU --> S3
    CPU --> PG
    GPU --> PG

    A1 --> OTEL
    A2 --> OTEL
    A3 --> OTEL
    CPU --> OTEL
    GPU --> OTEL

    OTEL --> PROM
    OTEL --> GRAF
    OTEL --> TRACE
```

## 42. Final Technology Decision

The concrete baseline is:

``` text
Python 3.13
FastMCP 4.x
MCP 2026-07-28
STDIO
Streamable HTTP
OAuth 2.1 / OIDC
JWT
Pydantic 2
SQLAlchemy 2
asyncpg
PostgreSQL 16+
Redis/Valkey
S3-compatible object storage
PyArrow
pandas
scikit-learn
XGBoost
LightGBM
CatBoost
asyncio
httpx
OpenTelemetry
Prometheus
Grafana
pytest
pytest-asyncio
Ruff
ty
uv
Docker/OCI
Terraform
GitHub Actions
Trivy
```

The most important architectural rule remains:

``` text
                    AI Agent
                       |
                       | MCP
                       v
                  ML-MCP Server
                       |
             validated experiment
                       |
                       v
                 Durable Queue
                       |
                       v
              Sandboxed ML Worker
                       |
                       v
              Immutable Artifacts
                       |
                       v
                 ML-MCP Server
                       |
                       v
                Analysis Agent
```

The MCP server remains small, deterministic and security-focused. ML
compute remains isolated and horizontally scalable. This separation is
what allows the project to grow from a model-testing MCP into a serious
agentic ML experimentation platform without turning the MCP endpoint
into an unsafe code-execution surface.

## 43. Official References

-   Model Context Protocol specification and 2026-07-28 release
    documentation: https://modelcontextprotocol.io/
-   MCP 2026-07-28 release notes:
    https://blog.modelcontextprotocol.io/posts/2026-07-28/
-   FastMCP: https://gofastmcp.com/
-   FastMCP 4 GA announcement: https://blog.gofastmcp.com/3mufbh2vcv22o
