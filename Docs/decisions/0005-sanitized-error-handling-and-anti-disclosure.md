# ADR-0005: Database Exception Sanitization and Anti-Disclosure Error Handling

## Status
Accepted

## Date
2026-09-19

## Context
When client agents invoke MCP tools with invalid inputs—such as referencing a non-existent `project_id`, `dataset_version_id`, or `model_version_id`—the underlying relational database (PostgreSQL via SQLAlchemy and asyncpg) raises exceptions such as `IntegrityError` (foreign key violation) or `DBAPIError`.

In early versions of the MCP server, unhandled or partially-handled database exceptions leaked raw internal details to the client:
```text
(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.ForeignKeyViolationError'>: 
insert or update on table "experiments" violates foreign key constraint "fk_experiments_projects"
DETAIL: Key (project_id)=(invalid-uuid) is not present in table "projects".
[SQL: INSERT INTO experiments (id, project_id, tenant_id, ...) VALUES ($1, $2, $3, ...)]
[parameters: ('01a0b...', 'invalid-uuid', 'default-tenant', ...)]
```

This caused two severe issues:
1. **Security Vulnerability (OWASP A01/A05 - Information Disclosure)**: Exposes internal schema names, table structures, column definitions, parameter types, and raw SQL queries.
2. **Poor Agent Experience**: Autonomous LLM agents parse text errors; raw SQL stack traces confuse agents rather than giving actionable feedback like `"Project 'invalid-uuid' not found"`.

## Decision
Implement centralized exception interception and sanitization in `_execute_secured` middleware:
1. **Foreign Key Violations**: Intercept `IntegrityError` where the underlying error is a foreign key constraint violation. Map it to a clean domain error:
   ```python
   ResourceNotFoundError(resource_type="Project/Dataset/Model", resource_id="specified in request")
   ```
2. **Unique Constraint Violations**: Intercept unique constraint violations (e.g. duplicate project or dataset name) and map to:
   ```python
   InvalidInputError("A resource with this name or identifier already exists.")
   ```
3. **General Database Errors**: Catch all other `DBAPIError` / database exceptions and return:
   ```python
   InvalidInputError("Database operation failed due to invalid input.")
   ```
4. **Pre-Execution Resource Checks**: In tools where specific parent entities are required (e.g., `create_experiment` and `register_dataset`), perform explicit existence checks (`await project_repo.get_project(project_id)`) before attempting writes, returning an explicit `ResourceNotFoundError("Project", project_id)`.

## Consequences
- **Positive**:
  - Zero information disclosure: raw SQL strings, table names, and query dumps are completely stripped from client responses.
  - LLM agents receive clear, deterministic error messages explaining exactly which resource was missing or duplicate.
  - Verified by integration tests (`tests/integration/test_test_report_remediation.py`).
- **Negative / Trade-offs**:
  - Developers debugging database issues in tests or local development must inspect server container logs (`docker logs modellab-mcp-api`) where full tracebacks are logged at `ERROR` level, rather than seeing them directly in MCP client tool responses.
