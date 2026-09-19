# ADR-0006: First-Class Project Management and Workspace Hierarchy

## Status
Accepted

## Date
2026-09-19

## Context
ModelLab's data model defined a top-level `Project` entity (`projects` table in PostgreSQL), and both `experiments` and `datasets` possessed foreign keys pointing to `projects.id`.

However, the FastMCP tool catalog initially lacked tools for project lifecycle management:
- No `create_project` tool existed to initialize workspaces.
- No `list_projects` tool existed to allow agents to discover active workspaces.
- On cold startup, the `projects` table was empty; agents attempting to run experiments without a known `project_id` failed with foreign key errors.
- Calling `list_experiments(project_id="non-existent")` returned an empty list `[]` instead of signaling that the project did not exist, concealing client errors.

## Decision
Elevate projects to first-class citizens in ModelLab's architecture:
1. **FastMCP Tools**:
   - `create_project(name, description)`: Creates a new project workspace under the caller's `tenant_id`.
   - `list_projects(limit, offset)`: Lists active projects accessible to the caller.
2. **Startup Auto-Seeding**: During application startup lifespan (`app_lifespan`), automatically seed a `"Default Project"` (`default-project`) for `default-tenant` if none exists, ensuring zero-configuration readiness for local development and initial testing.
3. **Strict Project Validation**:
   - Tools accepting `project_id` (`create_experiment`, `register_dataset`, `list_experiments`, `list_datasets`) explicitly verify that the project exists.
   - If the project does not exist, raise `ResourceNotFoundError("Project", project_id)` rather than silently returning an empty list.
4. **RBAC Integration**: Add `Scope.PROJECTS_READ` and `Scope.PROJECTS_WRITE` to the security model, granting appropriate permissions across Viewer, Researcher, Operator, and Admin roles.

## Consequences
- **Positive**:
  - Clean hierarchical organization: `Tenant` $\rightarrow$ `Project` $\rightarrow$ `Datasets` & `Experiments` $\rightarrow$ `Runs` & `Artifacts`.
  - Autonomous agents can explore existing projects or create dedicated workspaces for specific ML exploration tasks.
  - Zero cold-start blockage: `"Default Project"` is immediately available out-of-the-box.
- **Negative / Trade-offs**:
  - Tool catalog expanded from 21 to 23 tools, slightly increasing tool discovery payload size (well within client limits).
