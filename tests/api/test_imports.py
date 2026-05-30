"""Tests for POST /imports — router contract.

We mock ``ingest_file`` because the production implementation uses postgres
``ON CONFLICT`` which is unsupported by the SQLite test DB. The actual parser
behavior is covered by ``tests/ingestion/test_pekao.py`` etc.
"""
import io
import json

import pytest

from finance.domain.dto import ImportSummary
from finance.domain.enums import BankSource
from finance.ingestion import ParseError


@pytest.fixture
def _patch_ingest(monkeypatch):
    calls: list[dict] = []

    def fake_ingest(session, *, source, filename, stream, parser=None):
        calls.append(
            {
                "source": source,
                "filename": filename,
                "bytes": stream.read(),
                "parser": parser,
            }
        )
        return ImportSummary(
            import_id=1,
            source=BankSource(source) if not isinstance(source, BankSource) else source,
            total_rows=3,
            inserted=2,
            duplicates=1,
        )

    from apps.api.routers import imports as imports_router

    monkeypatch.setattr(imports_router, "ingest_file", fake_ingest)
    return calls


def test_upload_returns_summary(client, _patch_ingest) -> None:
    r = client.post(
        "/imports",
        files={"file": ("pekao.csv", io.BytesIO(b"col1;col2\n1;2\n"), "text/csv")},
        data={"source": "pekao"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["inserted"] == 2
    assert body["duplicates"] == 1
    assert body["total_rows"] == 3
    assert len(_patch_ingest) == 1
    assert _patch_ingest[0]["filename"] == "pekao.csv"


def test_upload_invalid_source_400_or_422(client, _patch_ingest) -> None:
    r = client.post(
        "/imports",
        files={"file": ("x.csv", io.BytesIO(b"x"), "text/csv")},
        data={"source": "not-a-bank"},
    )
    assert r.status_code in (400, 422)


def test_upload_parse_error_returns_422(client, monkeypatch) -> None:
    def boom(session, *, source, filename, stream, parser=None):
        raise ParseError("bad header")

    from apps.api.routers import imports as imports_router

    monkeypatch.setattr(imports_router, "ingest_file", boom)
    r = client.post(
        "/imports",
        files={"file": ("x.csv", io.BytesIO(b"garbage"), "text/csv")},
        data={"source": "pekao"},
    )
    assert r.status_code == 422
    assert "bad header" in r.json()["detail"]


def test_upload_not_implemented_returns_501(client, monkeypatch) -> None:
    def boom(session, *, source, filename, stream, parser=None):
        raise NotImplementedError("nordigen not wired")

    from apps.api.routers import imports as imports_router

    monkeypatch.setattr(imports_router, "ingest_file", boom)
    r = client.post(
        "/imports",
        files={"file": ("x.csv", io.BytesIO(b"x"), "text/csv")},
        data={"source": "nordigen"},
    )
    assert r.status_code == 501


# ---------------------------------------------------------------------------
# /imports/preview + auto-detection
# ---------------------------------------------------------------------------

_PEKAO_HEADERS = (
    b"Data ksi\xeagowania;Data waluty;Nadawca / Odbiorca;Adres nadawcy / odbiorcy;"
    b"Rachunek \xb9r\xf3d\xb3owy;Rachunek docelowy;Tytu\xb3em;Kwota operacji;Waluta;"
    b"Numer referencyjny;Typ operacji;Kategoria\r\n"
    b"01.04.2026;01.04.2026;Carrefour;ul. Testowa 1;'12345;'67890;Zakupy;-50,00;PLN;"
    b"REF1;Karta;\xbbywno\xb6\xe6\r\n"
)
_GENERIC_EN = (
    b"Date,Amount,Currency,Description,Memo\n"
    b"2026-04-01,-50.00,PLN,Carrefour,Groceries\n"
    b"2026-04-02,3000.00,PLN,Acme Corp,Salary\n"
)


def test_preview_returns_headers_and_detection(client) -> None:
    r = client.post(
        "/imports/preview",
        files={"file": ("any.csv", io.BytesIO(_GENERIC_EN), "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert "Date" in body["headers"]
    assert "Amount" in body["headers"]
    assert body["delimiter"] == ","
    assert body["detected_source"] is None  # not Pekao/Revolut
    assert body["detected_mapping"]["date"] == "Date"
    assert body["detected_mapping"]["amount"] == "Amount"
    assert body["detected_mapping"]["currency"] == "Currency"
    assert len(body["sample_rows"]) == 2


def test_preview_detects_pekao(client) -> None:
    r = client.post(
        "/imports/preview",
        files={"file": ("pekao.csv", io.BytesIO(_PEKAO_HEADERS), "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["detected_source"] == "pekao"


def test_preview_empty_file_422(client) -> None:
    r = client.post(
        "/imports/preview",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 422


def test_upload_auto_detects_pekao(client, _patch_ingest) -> None:
    """When source is omitted, headers map to Pekao and that's what's used."""
    r = client.post(
        "/imports",
        files={"file": ("export.csv", io.BytesIO(_PEKAO_HEADERS), "text/csv")},
    )
    assert r.status_code == 200
    assert _patch_ingest[0]["source"] == BankSource.PEKAO
    assert _patch_ingest[0]["parser"] is None  # registered parser used


def test_upload_auto_falls_back_to_generic(client, _patch_ingest) -> None:
    r = client.post(
        "/imports",
        files={"file": ("any.csv", io.BytesIO(_GENERIC_EN), "text/csv")},
    )
    assert r.status_code == 200
    assert _patch_ingest[0]["source"] == BankSource.UNKNOWN
    # generic parser was constructed and passed in
    from finance.ingestion.generic import GenericCsvParser

    assert isinstance(_patch_ingest[0]["parser"], GenericCsvParser)


def test_upload_generic_with_explicit_column_map(client, _patch_ingest) -> None:
    cmap = {"date": "Date", "amount": "Amount", "merchant": "Description"}
    r = client.post(
        "/imports",
        files={"file": ("x.csv", io.BytesIO(_GENERIC_EN), "text/csv")},
        data={"source": "generic", "column_map": json.dumps(cmap)},
    )
    assert r.status_code == 200
    parser = _patch_ingest[0]["parser"]
    assert parser is not None and parser.column_map == cmap


def test_upload_generic_invalid_column_map_422(client, _patch_ingest) -> None:
    r = client.post(
        "/imports",
        files={"file": ("x.csv", io.BytesIO(_GENERIC_EN), "text/csv")},
        data={"source": "generic", "column_map": "{not-json"},
    )
    assert r.status_code == 422
