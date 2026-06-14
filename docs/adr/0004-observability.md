# ADR-0004: Lightweight Observability With structlog And Health Checks

- **Status:** ACCEPTED
- **Date:** 2026-05-01

## Context

The app is self-hosted through Docker Compose on a single host. Required
diagnostic signals:

- **Logs:** contextual JSON logs with request id, user and path.
- **Health checks:** quick diagnosis of database, Ollama and process readiness.
- **Tracing:** optional; on one host, request-id correlation is enough.

## Decision

- **Logs:** use `structlog` with JSON processors and `bind_contextvars`; assign
  a UUID to each request. Echo `X-Request-ID` on input and output.
- **Health:** expose public `/health`, `/health/live`, `/health/ready`.
- **Prometheus metrics:** not included. `/metrics`, Prometheus middleware and
  Grafana dashboards were removed as excessive for a single-user demo.
- **Tracing:** no OpenTelemetry. It adds too much operational overhead for the
  single-node thesis setup.

## Consequences

**Positive:**

- Fewer runtime dependencies and fewer components to explain.
- No public `/metrics` endpoint, so the exposed surface is smaller.
- Debugging remains practical with `request_id`, health checks and
  `docker logs`.

**Negative:**

- No RED dashboard or historical metrics without adding an external stack.
- Endpoint profiling becomes harder if the project grows beyond a single-host
  demo.

## Rejected Alternatives

- **Prometheus + Grafana.** Useful for multi-user production systems, but too
  complex for this project.
- **OpenTelemetry SDK** for logs, metrics and traces. More complexity and a
  collector requirement. It can be added later without changing domain logic.
- **Sentry.** Unnecessary for a single-user local deployment.
- **ELK stack.** Overkill; `docker logs` plus `jq` is enough for iteration.
