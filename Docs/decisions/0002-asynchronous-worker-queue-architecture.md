# ADR-0002: Asynchronous Worker Queue Architecture for ML Training

## Status
Accepted

## Date
2026-09-19

## Context
Machine learning training tasks (e.g., LightGBM, XGBoost, CatBoost, Random Forest, Multi-Layer Perceptrons) on large tabular datasets (20k–50k+ rows, 10–55 features) require significant CPU, memory, and wall-clock execution time (1–10+ seconds per model).

Handling model training synchronously within HTTP MCP tool calls causes severe architectural issues:
1. **Thread Starvation**: Python web workers (Uvicorn / FastAPI) block during heavy C-extension computations (OpenMP threads in XGBoost/LightGBM).
2. **Client Timeouts**: MCP clients typically enforce 10–60 second request timeouts. Heavy hyperparameter tuning or large ensembles easily exceed this threshold.
3. **Loss of Fault Tolerance**: If an API server crashes or restarts during a training run, in-memory training state is lost with no retry mechanism.
4. **Lack of Backpressure**: A burst of concurrent training requests can exhaust server CPU and memory, crashing the entire MCP process.

## Decision
Decouple MCP tool handling from model training using an **Asynchronous Task Queue** pattern:
1. **Enqueueing**: `create_experiment` records the experiment in PostgreSQL with status `QUEUED`, writes a task payload to a Redis list (`modellab:tasks:tabular`), and immediately returns a lightweight response (`experiment_id`, `status: "QUEUED"`, submission latency < 30ms).
2. **Execution Worker**: A dedicated background worker process (`ml-worker-tabular-cpu`) consumes tasks from Redis using reliable popping (`BLMOVE`/`RPOPLPUSH`), transitions status to `RUNNING`, executes model training in an isolated process context, and records metrics in PostgreSQL.
3. **Artifact Storage**: Serialized model binaries (`model.joblib`), evaluation predictions (`predictions.parquet`), and confusion matrices are written directly to MinIO/S3 object storage under tenant-isolated paths.
4. **Status Polling & Notifications**: Clients track progress via `get_experiment` or receive SSE status updates when the run transitions to `SUCCEEDED` or `FAILED`.

## Alternatives Considered

### Synchronous Training in FastMCP Handler
- **Pros**: Simple, no external queue or worker services required.
- **Cons**: Blocks API threads, crashes on memory exhaustion, impossible to scale workers independently from the API.
- **Rejected**: Incompatible with production ML requirements.

### Celery / RQ
- **Pros**: Mature Python task queues.
- **Cons**: Heavy dependencies, complex configuration, awkward integration with asyncio in modern FastAPI codebases.
- **Rejected**: Redis list + asyncio consumer provides minimal overhead, zero bloat, and full control over concurrency limits.

## Consequences
- **Positive**:
  - API response times for `create_experiment` drop to sub-30ms regardless of dataset size.
  - Workers can be scaled horizontally (independent worker containers) across separate GPU/CPU nodes.
  - Redis backpressure prevents server crashes during burst experiment submissions (demonstrated 4-job burst drained in 1.62s).
- **Negative / Trade-offs**:
  - Requires Redis and MinIO S3 infrastructure services.
  - Client agents must poll `get_experiment` or listen to SSE events to await completion before running downstream diagnostics.
