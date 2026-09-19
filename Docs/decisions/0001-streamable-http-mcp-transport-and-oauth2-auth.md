# ADR-0001: Streamable HTTP Transport for MCP with OAuth 2.1 Authentication

## Status
Accepted

## Date
2026-09-19

## Context
The Model Context Protocol (MCP) specification defines two primary communication transports:
1. **Stdio (Standard Input / Output)**: Server processes communicate with the client agent through pipes on the same operating system instance.
2. **Streamable HTTP (Server-Sent Events / SSE + JSON-RPC over HTTP POST)**: Server runs as a web service, communicating with client agents over HTTP networks.

In enterprise ML environments and containerized microservices architectures, Stdio presents major operational limitations:
- **Coupling to Host**: Stdio requires client agents and server processes to run on the identical virtual machine or container.
- **Microservice Isolation**: Databases (PostgreSQL), caches (Redis), and object stores (MinIO/S3) reside in dedicated containers; running an MCP server inside Docker requires network accessibility.
- **Horizontal Scaling & Load Balancing**: Stdio cannot be load-balanced behind reverse proxies (NGINX, Traefik) or Kubernetes ingress.
- **Authentication**: Stdio provides no standardized transport-layer security or authorization tokens.

## Decision
Implement **Streamable HTTP** (`/mcp`) alongside Stdio as the primary network transport for ModelLab MCP:
1. **Endpoint**: Expose `http://<host>:<port>/mcp` using FastAPI and Starlette SSE streaming.
2. **Session Lifecycle**: Clients initialize via POST, receive a `session_id`, and establish an SSE channel (`GET /mcp`) for asynchronous notifications and server-to-client events.
3. **Authentication**: Enforce OAuth 2.1 Bearer Token validation in the HTTP Authorization header (`Authorization: Bearer <jwt>`) using RS256/EdDSA JWT signature verification.
4. **Tool Discovery**: Expose all 23 FastMCP tools over standard JSON-RPC 2.0 requests dispatched over HTTP POST.

## Alternatives Considered

### Stdio-Only
- **Pros**: Zero network overhead, simple local invocation.
- **Cons**: Cannot run in Docker/Kubernetes while accessed by local or remote IDE agents; no native network multi-tenancy.
- **Rejected**: Prevents containerized enterprise deployment.

### WebSockets
- **Pros**: Bidirectional, persistent single connection.
- **Cons**: Not the standard transport for MCP 2024+ specifications; firewall/proxy traversal is more complex than HTTP/SSE.
- **Rejected**: Standard MCP clients natively implement Streamable HTTP (SSE + POST).

## Consequences
- **Positive**:
  - ModelLab can run in Docker Compose or Kubernetes clusters while agents interact over HTTP.
  - Multi-tenant agents can authenticate independently with distinct roles and scopes.
  - Standard monitoring, health checks (`/health/live`, `/health/ready`), and OpenTelemetry tracing work natively.
- **Negative / Trade-offs**:
  - Requires maintaining session state in memory/Redis.
  - Network latency (1–2 ms per RPC call) compared to local OS pipes.
