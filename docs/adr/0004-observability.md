# ADR-0004: Lekka obserwowalność — structlog + health checks, bez Prometheus

- **Status:** ACCEPTED
- **Data:** 2026-05-01

## Kontekst

Aplikacja działa w trybie self-hosted (Docker Compose, jeden host).
Wymagane sygnały diagnostyczne:

- **Logi** — kontekstowe (request-id, user, path), JSON dla parsowalności.
- **Health checks** — szybka diagnoza DB, Ollama i gotowości procesu.
- **Trace** — opcjonalne; przy 1 hoście korelacja po request-id wystarcza.

## Decyzja

- **Logi:** `structlog` z processorami JSON, korelacja przez `bind_contextvars`
  z UUID na każde żądanie. Header `X-Request-ID` na wejściu i wyjściu.
- **Health:** publiczne `/health`, `/health/live`, `/health/ready`.
- **Metryki Prometheus:** brak. Endpoint `/metrics`, middleware Prometheus i
  dashboard Grafany zostały usunięte jako nadmiarowe dla single-user demo.
- **Tracing:** **brak OpenTelemetry**. Zbyt duży narzut dla single-node
  setupu i poza zakresem pracy magisterskiej.

## Konsekwencje

**Pozytywne:**

- Mniej zależności runtime i mniej elementów do tłumaczenia podczas obrony.
- Brak publicznego `/metrics`, więc mniejsza powierzchnia ekspozycji.
- Debugowanie nadal jest praktyczne przez `request_id`, health checks i
  `docker logs`.

**Negatywne:**

- Brak dashboardu RED i historycznych metryk bez dołożenia zewnętrznego stosu.
- Trudniejsze profilowanie endpointów, jeśli projekt rozrośnie się poza
  single-host demo.

## Alternatywy odrzucone

- **Prometheus + Grafana.** Dobre dla produkcji wieloużytkownikowej, ale
  w tym projekcie zwiększało złożoność bardziej niż wartość demonstracyjną.
- **OpenTelemetry SDK** (logs + metrics + traces). Większa złożoność,
  wymaga collectora. Można dodać później bez zmian w logice domenowej.
- **Sentry** dla błędów. Płatny w skali, niepotrzebny przy 1 użytkowniku.
- **ELK stack.** Overkill — `docker logs` + `jq` wystarczy do iteracji.
