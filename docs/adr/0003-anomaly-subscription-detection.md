# ADR-0003: Detekcja anomalii i abonamentów — hybryda klasyczna, bez deep learning

- **Status:** ACCEPTED
- **Data:** 2026-05-01

## Kontekst

Dwa rdzeniowe wymagania funkcjonalne:

1. **Anomalia** — wykryć transakcję istotnie odbiegającą od historii kategorii
   (np. zakup AGD w „food” lub 5× średnia w „transport”).
2. **Abonament** — wykryć powtarzalne obciążenia (Netflix, Orange Flex) o
   stabilnej kwocie i kadencji 7/30/90/365 dni, mimo zmieniającego się
   merchant string.

Dataset użytkownika: 12–36 mies. historii, ~3–6k transakcji, 8 kategorii
wydatków plus osobna flaga `is_transfer`.
Każda kategoria ma 50–800 obserwacji.

## Decyzja

**Hybrydowa metoda klasyczna**, bez autoencoderów i bez embeddingów LLM:

- **Anomalie** — IsolationForest na prostych, jawnych cechach liczbowych
  (`log_abs`, dzień tygodnia/miesiąca, frequency merchanta, kierunek) +
  `Robust Z-score` (median + MAD) per `(category, direction)` + reguła
  „nowy merchant + duża kwota”.
- **Abonamenty** — *period detection* na sekwencji dat dla danej (znormalizowanej)
  nazwy merchanta: medianowy odstęp + tolerancja kwoty ±10 %, domyślnie
  minimum 2 wystąpienia w krótkim oknie danych.

## Konsekwencje

**Pozytywne:**

- Czytelne uzasadnienia — w UI pokazujemy powody typu „nietypowo wysoka
  kwota (z=4.8)” albo „nowy odbiorca + duża kwota”.
- Brak GPU i brak zewnętrznego serwisu ML.
- Stabilność na małych podpopulacjach (MAD jest robustny na outliery, czego
  z-score klasyczny nie gwarantuje).
- IsolationForest łapie przypadki wielowymiarowe, których sam z-score nie
  wykryje.

**Negatywne:**

- IsolationForest jest mniej interpretowalny niż czysty z-score, dlatego wynik
  jest łączony z powodami regułowymi i robust z-score.
- Detektor abonamentów nie złapie zmiennych kwot (Bolt). Świadoma decyzja:
  zmienne kwoty to nie abonament w sensie produktowym.

## Alternatywy odrzucone

- **Czysty robust z-score.** Bardzo interpretowalny, ale pomija przypadki typu
  „nowy merchant + nietypowy wzorzec”.
- **LOF / embedding-based outlier detection.** Większa złożoność, słabsza
  kontrola nad interpretacją i brak potrzeby przy tej skali danych.
- **Autoencoder na embeddingach merchantów.** Overkill dla skali datasetu.
- **Prophet do detekcji anomalii.** Detekcja transakcyjna i prognozowanie
  miesięczne to różne problemy; Prophet nie jest potrzebny w runtime.

## Mierniki sukcesu

- Precyzja anomalii ≥ 0.8 na ręcznie oznaczonym subsecie 50 transakcji
  (false-positive rate kontrolowany progiem |z|).
- Recall abonamentów ≥ 0.9 dla rzeczywistego zbioru znanych subskrypcji
  użytkownika.
