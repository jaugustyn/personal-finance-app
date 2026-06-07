# Notatki Do Prezentacji Projektu

Ten plik jest skrótem do opowiedzenia aplikacji podczas prezentacji. Celem nie
jest czytanie go słowo w słowo, tylko szybkie przypomnienie: co pokazać, co
powiedzieć technicznie i gdzie w projekcie występuje ML/AI.

## 1. Idea Projektu

Aplikacja jest self-hostowanym systemem do zarządzania finansami osobistymi.
Łączy import danych bankowych, reguły deterministyczne, modele ML i lokalnego
asystenta językowego. Ważne założenie: twarde liczby są liczone przez backend,
a LLM może je tylko opisać po polsku.

Najważniejsze elementy:

- import i deduplikacja transakcji z plików bankowych,
- typowanie transakcji, np. zakup, przelew własny, pensja, opłata bankowa,
- klasyfikacja kategorii wydatkowych,
- centrum pracy nad jakością etykiet treningowych,
- prognozowanie wydatków,
- wykrywanie anomalii,
- wykrywanie subskrypcji,
- lokalny asystent finansowy oparty o routing i narzędzia deterministyczne.

## 2. Pulpit

Co pokazuje:

- KPI: przychody, wydatki, saldo netto, średnia miesięczna,
- cash flow w czasie,
- top wydatki pogrupowane po odbiorcy,
- najczęstsze wydatki,
- trend wydatków wg kategorii,
- zmianę miesiąc do miesiąca,
- skumulowane saldo,
- ostatnie transakcje.

Co powiedzieć:

- Pulpit jest widokiem syntetycznym, nie miejscem do trenowania modeli.
- Zakres danych można przełączyć między ostatnimi 12 miesiącami i wszystkimi
  danymi.
- Top wydatki są agregowane po znormalizowanej nazwie odbiorcy. To ogranicza
  problem wariantów typu `LIDL 1234`, `Lidl sp. z o.o.` itd.
- Pulpit domyślnie wyklucza przelewy własne, żeby nie zaburzały wydatków.

## 3. Transakcje

Co pokazuje:

- pełną listę transakcji,
- kierunek, kwotę, odbiorcę, tytuł, kategorię i typ transakcji,
- sugestie ML z confidence,
- notatki i tagi,
- operacje masowe.

Co powiedzieć:

- `transaction_type` opisuje semantykę przepływu pieniędzy, np. zakup,
  przelew własny, pensja, zwrot.
- `category` opisuje budżetową kategorię wydatku, np. jedzenie, transport,
  zdrowie.
- Typ transakcji i kategoria to dwie różne warstwy. Przykład: pensja ma typ
  `salary`, ale nie powinna dostać kategorii wydatkowej.
- Sugestie ML nie są automatycznie traktowane jako prawda. Użytkownik może je
  zaakceptować albo odrzucić.
- Zaakceptowane i ręcznie nadane kategorie stają się danymi treningowymi.

## 4. Import Danych

Co pokazuje:

- import pliku bankowego,
- mapowanie kolumn,
- walidację wymaganych pól,
- historię importów,
- deduplikację transakcji.

Co powiedzieć:

- Parsery bankowe zamieniają różne formaty eksportu na wspólny model
  transakcji.
- Deduplikacja bazuje na stabilnym hashu z pól transakcji, więc ponowny import
  tego samego pliku nie powinien dublować rekordów.
- Już podczas importu działają reguły typowania transakcji i reguły personalne.
- Runtime importu nadal używa reguł deterministycznych do `transaction_type`,
  a model typu transakcji jest traktowany jako evidence/eksperyment ML.

## 5. Kategorie

Co pokazuje:

- listę kategorii głównych,
- kolory kategorii używane na wykresach,
- dodawanie własnych kategorii.

Co powiedzieć:

- Kategorie główne są docelową etykietą modelu klasyfikacji wydatków.
- Podkategorie mogą doprecyzowywać opis wydatku, ale główny model ML operuje
  na kategoriach głównych.
- Kolory kategorii są częścią prezentacji danych, nie częścią modelu.

## 6. Jakość Danych

Co pokazuje:

- transakcje bez kategorii,
- transakcje bez sugestii,
- sugestie o niskim confidence,
- rzadkie klasy,
- powtarzalnych odbiorców bez reguły,
- panel `Co zrobić teraz`.

Co powiedzieć:

- To jest centrum pracy nad danymi treningowymi.
- Model klasyfikacji jest tak dobry, jak dane potwierdzone przez użytkownika.
- Rzadkie klasy są problemem w klasyfikacji wieloklasowej, bo model ma mało
  przykładów i łatwo je myli.
- Celem przed retrainingiem jest zwiększenie liczby potwierdzonych etykiet,
  szczególnie w słabszych klasach.

## 7. Modele ML

Co pokazuje:

- status aktywnego modelu,
- liczbę etykiet,
- klasy znane modelowi,
- Macro-F1,
- porównanie eksperymentów treningowych,
- feedback loop,
- najczęstsze pomyłki,
- przyciski `Przetrenuj model` i `Przelicz sugestie`.

Co powiedzieć:

- To nie jest ręczny przełącznik modeli.
- Aktywny model zmienia się po retrainingu i zapisaniu nowego artefaktu.
- `Przetrenuj model` buduje nowy artefakt na potwierdzonych danych.
- `Przelicz sugestie` używa aktualnego modelu do ponownego wyliczenia sugestii
  dla transakcji.
- Macro-F1 jest ważne, bo przy nierównych klasach pokazuje jakość także dla
  rzadkich kategorii, a nie tylko dla dominujących.
- Porównanie z baseline'em typu dummy jest potrzebne, żeby pokazać, że model
  uczy się czegoś więcej niż najczęstszej klasy.

## 8. ML: Klasyfikacja Kategorii

Cel:

- przypisanie transakcji wydatkowej do jednej z kategorii budżetowych.

Dane wejściowe:

- odbiorca,
- tytuł/opis,
- kwota,
- kierunek transakcji,
- cechy kontekstowe, np. typ transakcji i źródło.

Podejście:

- klasyfikacja nadzorowana wieloklasowa,
- cechy tekstowe oparte o TF-IDF,
- proste cechy numeryczne i kategoryczne,
- porównanie modeli i baseline'ów,
- raportowanie Macro-F1, Weighted-F1, per-class metrics i confusion matrix.

Jak to obronić:

- TF-IDF jest sensownym wyborem w tym projekcie, bo nazwy odbiorców i tytuły
  przelewów są krótkimi tekstami z powtarzalnymi wzorcami.
- Nie trzeba od razu używać embeddingów, jeżeli prostszy model daje czytelny
  i mierzalny baseline.
- Model nie powinien trenować się na własnych niepotwierdzonych predykcjach.
  Do treningu używane są kategorie potwierdzone ręcznie lub zaakceptowane przez
  użytkownika.

## 9. ML: Klasyfikacja Typu Transakcji

Cel:

- osobna analiza wieloklasowa dla `transaction_type`.

Klasy:

- `purchase`,
- `own_transfer`,
- `person_transfer`,
- `salary`,
- `income`,
- `refund`,
- `cash_withdrawal`,
- `debt_payment`,
- `bank_fee`,
- `savings_investment`,
- `other`.

Dane wejściowe:

- odbiorca,
- tytuł,
- surowa kategoria z banku,
- kwota bezwzględna,
- kierunek,
- źródło danych.

Ważne ograniczenie:

- w v1 to jest eksperyment evidence-only,
- etykiety pochodzą z obecnego `Transaction.transaction_type`,
- są to silver labels, bo wynikają z reguł i danych runtime,
- model nie zastępuje jeszcze `detect_transaction_type` w imporcie.

Jak to obronić:

- spełnia wymaganie wieloklasowej analizy ML dla typu transakcji,
- ale nie ryzykuje popsucia działania produkcyjnego importu,
- pozwala porównać model ML z regułami i zebrać metryki do raportu.

## 10. Prognoza

Co pokazuje:

- prognozę wydatków na kolejne miesiące,
- wybór kategorii lub wszystkie kategorie,
- horyzont prognozy,
- model i długość historii.

Co powiedzieć:

- Forecasting działa na miesięcznych szeregach wydatków.
- Dla małej ilości historii prognoza jest poglądowa.
- Najsensowniej prezentować prognozę dla wszystkich kategorii, bo ma więcej
  danych i jest stabilniejsza.
- Dla pojedynczych kategorii prognoza ma sens dopiero, gdy dana kategoria ma
  regularną historię.

Modele:

- proste baseline'y czasowe,
- m.in. mean/naive oraz metody typu SES/ARIMA w evidence.

Jak to obronić:

- Celem nie jest idealny model produkcyjny, tylko poprawny eksperyment
  time-series z baseline'ami.
- Przy finansach osobistych dane są krótkie i zaszumione, więc prosty model
  często jest bardziej wiarygodny niż zbyt skomplikowany.

## 11. Podsumowanie Okresu

Co pokazuje:

- porównanie bieżącego tygodnia lub miesiąca z analogicznym poprzednim okresem,
- przychód, wydatki i saldo netto,
- największe zmiany kategorii,
- największych sprzedawców,
- przekroczenia limitów,
- postęp celu oszczędnościowego.

Co powiedzieć:

- To jest część deterministyczna, nie LLM.
- Tydzień oznacza bieżący tydzień kalendarzowy od poniedziałku do dziś.
- Miesiąc oznacza bieżący miesiąc od 1. dnia do dziś, porównany z pełnym
  poprzednim miesiącem.
- Jeżeli w bieżącym miesiącu nie ma danych, wartości bieżące są zerowe, a
  zmiana pokazuje różnicę względem poprzedniego okresu.

## 12. Anomalie

Co pokazuje:

- transakcje wymagające sprawdzenia,
- typ anomalii,
- priorytet,
- powody flagowania,
- feedback: trafne, nietrafne, ignoruj odbiorcę.

Podejście ML:

- element nienadzorowany: IsolationForest,
- uzupełniony regułami biznesowymi,
- przykłady reguł: bardzo duża kwota, nietypowa kwota dla odbiorcy, brak
  kategorii lub odbiorcy przy dużej transakcji.

Co powiedzieć:

- IsolationForest pomaga znaleźć nietypowe punkty bez ręcznych etykiet.
- Same modele nienadzorowane potrafią generować szum, dlatego wynik jest
  wzmacniany regułami i feedbackiem użytkownika.
- Feedback nie usuwa transakcji. On informuje system, czy podobne przypadki
  mają mieć wyższy lub niższy priorytet.

Nietypowy wzorzec (model) oznacza anomalię wskazaną głównie przez model IsolationForest.

Czyli transakcja niekoniecznie łamie prostą regułę typu „bardzo duża kwota” albo „brak kategorii”, ale jej kombinacja cech wygląda nietypowo względem reszty danych, np. kwota, kategoria, odbiorca, częstotliwość albo kontekst transakcji.

W skrócie: model uznał ją za odstającą, ale bez mocnego prostego wyjaśnienia regułowego.

## 13. Subskrypcje

Co pokazuje:

- powtarzalne płatności,
- szacowany koszt miesięczny,
- ostatnie wystąpienie,
- confidence.

Podejście:

- detekcja kadencji transakcji,
- analiza powtarzalnego odbiorcy i podobnych kwot,
- wykluczanie przelewów własnych i typów, które nie są wydatkami.

Co powiedzieć:

- To nie jest klasyfikator tekstowy, tylko detektor wzorców czasowych.
- Dla finansów osobistych subskrypcje są dobrym przykładem rekomendacji
  oszczędnościowej, bo są cykliczne i łatwe do przejrzenia.

## 14. Portfel

Co pokazuje:

- portfel inwestycyjny,
- pozycje, ilość, cena, wartość w PLN,
- P/L,
- historię wartości,
- przepływ przychody -> kategorie -> sprzedawcy.

Co powiedzieć:

- To jest rozszerzenie aplikacji poza same transakcje bankowe.
- Ceny mogą pochodzić z zewnętrznego źródła, np. yfinance.
- W demo nie trzeba skupiać się na tym jako na głównej części ML.

## 15. Asystent

Co pokazuje:

- pytania po polsku o finanse,
- odpowiedzi oparte na narzędziach backendowych,
- przykłady: wydatki w miesiącu, top kategorie, subskrypcje, rekomendacje.

Najważniejszy punkt:

- To nie jest czysty vector RAG do liczenia faktów.
- Projekt używa podejścia hybrydowego:
  - routing intencji,
  - deterministyczne narzędzia do liczenia danych,
  - lokalny LLM do opisania wyniku językiem naturalnym.

Jak to obronić:

- Pytanie typu `Na co najwięcej wydałem w styczniu 2026?` wymaga zapytania do
  danych, nie wyszukiwania podobnych dokumentów w wektorach.
- Dlatego twarde fakty liczy backend, a LLM nie powinien ich wymyślać.
- To jest bardziej bezpieczne i łatwiejsze do testowania niż czysty RAG.

## 16. Ustawienia

Co pokazuje:

- profil lokalny,
- walutę,
- dzień wypłaty,
- reguły personalne.

Co powiedzieć:

- Reguły personalne działają przed ML.
- Mogą sugerować kategorię lub typ transakcji albo automatycznie je stosować.
- Przykład: jeżeli odbiorca zawiera konkretną nazwę, można automatycznie
  traktować transakcję jako przelew własny albo przypisać kategorię.
- To jest świadome połączenie reguł i ML: proste, pewne przypadki obsługują
  reguły, a niepewne trafiają do modelu i review.

## 17. Evidence Package I Raporty

Co powiedzieć:

- Projekt generuje pakiet evidence do oceny ML/AI.
- Główny raport zbiorczy to `evidence_package`.
- Raport rozdziela:
  - klasyfikację kategorii,
  - klasyfikację typu transakcji,
  - forecasting,
  - anomaly detection,
  - subscriptions,
  - privacy check.

Ważne:

- Raporty publiczne nie powinny zawierać surowych nazw odbiorców ani tytułów.
- Do prezentacji najlepiej cytować `summary.md` i metryki zbiorcze, a nie
  prywatne eksporty bankowe.

## 18. Co Podkreślić Przy Obronach ML

Najmocniejsze punkty:

- Są dwa zadania supervised multiclass:
  - kategoria wydatku,
  - typ transakcji jako evidence-only na silver labels.
- Jest forecasting na miesięcznych szeregach.
- Jest unsupervised anomaly detection z IsolationForest.
- Jest detekcja subskrypcji jako analiza kadencji.
- Jest lokalny asystent LLM, ale z deterministycznymi narzędziami do faktów.
- Jest feedback loop: użytkownik akceptuje, odrzuca i ręcznie poprawia dane.
- Są metryki i baseline'y, a nie tylko demo UI.

Ograniczenia, które warto powiedzieć wprost:

- Jakość modeli zależy od liczby potwierdzonych etykiet.
- `transaction_type` ML jest eksperymentem evidence-only, nie produkcyjnym
  zamiennikiem reguł.
- Forecast dla krótkiej historii jest poglądowy.
- Anomalie nienadzorowane wymagają feedbacku, bo nietypowe nie zawsze znaczy
  błędne lub podejrzane.
- Dane finansowe są prywatne, dlatego raporty powinny być agregowane i
  anonimizowane.

## 19. Proponowana Kolejność Demo

1. Pulpit: pokaż przełącznik `12 miesięcy` / `Wszystkie dane`.
2. Import: pokaż mapowanie kolumn i deduplikację.
3. Transakcje: pokaż typ transakcji, kategorię, sugestię ML i accept/reject.
4. Jakość danych: pokaż, jak poprawiać dane treningowe.
5. Modele ML: pokaż status modelu, Macro-F1, retraining i reclassify.
6. Prognoza: pokaż forecast dla wszystkich kategorii.
7. Anomalie: pokaż typ anomalii i feedback.
8. Subskrypcje: pokaż cykliczne płatności.
9. Podsumowanie okresu: pokaż porównanie bieżącego okresu z poprzednim.
10. Asystent: zadaj pytanie po polsku o konkretne dane.

## 20. Krótkie Zdania Do Zapamiętania

- "Typ transakcji mówi, czym jest przepływ pieniędzy, a kategoria mówi, do
  jakiego koszyka budżetowego trafia wydatek."
- "LLM nie liczy faktów. Fakty liczy backend, a LLM je opisuje."
- "Jakość danych jest miejscem budowania lepszych etykiet treningowych."
- "Model kategorii jest produkcyjnie używany do sugestii, a model typu
  transakcji jest na razie eksperymentem evidence-only."
- "Anomalie są połączeniem IsolationForest, reguł biznesowych i feedbacku."
- "Forecast ma największy sens dla wszystkich kategorii i przy dłuższej
  historii."
