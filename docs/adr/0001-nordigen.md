# ADR-0001: Integracja z GoCardless Bank Account Data (dawniej Nordigen)

- **Status:** DEFERRED — odłożone poza zakres pracy magisterskiej. Zachowujemy szkielet kodu i klienta jako dowód koncepcji; decyzja ADOPT/REJECT po obronie.
- **Data:** 2026-05-01 (proposed) → 2026-05-15 (deferred)
- **Faza:** Faza 2 (decision gate) → realizacja przeniesiona poza zakres tezy

## Kontekst

Plan magisterski przewiduje opcjonalną integrację PSD2 do automatycznego pobierania
transakcji z banków, eliminując ręczny eksport CSV. Dostawca: GoCardless Bank Account
Data API (dawniej Nordigen). Free tier: 50 połączeń konta / miesiąc.

Banki używane przez użytkownika:

- **Pekao SA** — główne konto operacyjne (Pekao24).
- **Revolut** — konta multi-walutowe (PLN, USD).

## Decyzja

**DEFERRED** — z powodów wymienionych poniżej decyzja ADOPT/REJECT została odroczona. Zakres
funkcjonalny pracy magisterskiej (CSV ingest dla Pekao + Revolut, klasyfikator, anomalie,
forecasting, hybrydowy LLM) jest kompletny i mierzalny bez integracji PSD2.

### Powody odroczenia

1. **Free tier i limity rate-limit** — 50 połączeń/miesiąc, 90-dniowa rotacja zgody. Dla
   reprodukowalnych eksperymentów potrzebne byłyby fixtury offline → ich wartość poznawcza
   jest mała w stosunku do nakładu pracy.
2. **Cel pracy** — empiryczne porównanie metod ML (klasyfikacja, anomalie, prognozowanie)
   na danych transakcyjnych. Źródło danych (CSV vs PSD2) nie wpływa na wnioski naukowe.
3. **Powtarzalność** — anonimizowany dataset CSV jest powtarzalny i deterministyczny.
   Live PSD2 nie jest.

### Co zachowujemy

- Klient `src/finance/ingestion/nordigen.py` (mock-based) i jego testy jednostkowe
  pozostają w repo jako dowód, że architektura ingestion-registry pozwala dodać kolejne
  źródła bez zmian w warstwie domeny.
- Notebook PoC `notebooks/02_nordigen_poc.ipynb` jako artefakt do uruchomienia po obronie.
- Endpoint `POST /imports?source=nordigen` celowo zwraca **501 Not Implemented**.

| Pytanie                                                       | Odpowiedź         |
| ------------------------------------------------------------- | ----------------- |
| Czy Pekao SA jest na liście instytucji PL?                    | nie zweryfikowano |
| Czy Revolut jest dostępny (REVOLUT_REVOLT21 / REVOGB21)?      | nie zweryfikowano |
| `transaction_total_days` Pekao                                | nie zweryfikowano |
| `transaction_total_days` Revolut                              | nie zweryfikowano |
| Czy sandbox flow `SANDBOXFINANCE_SFIN0000` działa end-to-end? | nie zweryfikowano |
| Decyzja końcowa                                               | **DEFERRED**      |

## Konsekwencje

### Jeśli ADOPT

- Faza 5 dodaje: scheduler (APScheduler / cron w kontenerze API) → codzienny sync.
- Reconciliation z istniejącymi rekordami via `dedup_hash` (bez zmian w schemacie).
- Wymagana persystencja `requisition_id` per konto + obsługa wygasania zgody (90 dni).
- Sekrety: `NORDIGEN_SECRET_ID`, `NORDIGEN_SECRET_KEY` w `.env`.

### Jeśli DROP

- Pozostajemy przy CSV-only. Czas zaoszczędzony w Fazie 5 → ulepszony chat-LLM lub
  dodatkowy dashboard inwestycji (XTB/Degiro).
- ADR aktualizujemy do statusu `REJECTED` z uzasadnieniem (np. "Pekao SA brak na liście PL").

## Linki

- Notebook PoC: [notebooks/02_nordigen_poc.ipynb](../../notebooks/02_nordigen_poc.ipynb)
- Klient: [src/finance/ingestion/nordigen.py](../../src/finance/ingestion/nordigen.py)
- Testy: [tests/ingestion/test_nordigen.py](../../tests/ingestion/test_nordigen.py)
- Dokumentacja API: <https://developer.gocardless.com/bank-account-data/>
