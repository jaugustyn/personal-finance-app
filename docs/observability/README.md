# Lightweight Observability

Projekt świadomie używa lekkiej obserwowalności zamiast pełnego stosu
Prometheus/Grafana. Dla self-hosted single-user demo wystarczają logi
strukturalne, korelacja po `request_id` i endpointy health.

## Logi

API loguje do stdout przez `structlog`.

- `APP_ENV=dev` → czytelny console renderer.
- `APP_ENV` inne niż `dev` → JSON renderer.
- Każde żądanie dostaje `request_id`, `method`, `path`, `status` i
  `duration_ms`.
- Header `X-Request-ID` jest zwracany w odpowiedzi.

Przykład korelacji:

```bash
docker logs api | jq 'select(.request_id=="abc123")'
```

## Health checks

Publiczne endpointy diagnostyczne:

- `GET /health` — status aplikacji, DB i Ollama.
- `GET /health/live` — proces działa.
- `GET /health/ready` — aplikacja gotowa do obsługi ruchu, DB osiągalna.

## Czego nie ma świadomie

- `/metrics` i Prometheus — usunięte jako nadmiarowe dla zakresu pracy.
- Grafana dashboard — brak utrzymywanego dashboardu po usunięciu Prometheusa.
- Distributed tracing / OpenTelemetry — jeden host i request-id są wystarczające.
- Alerting — poza zakresem pracy magisterskiej i self-hosted demo.
