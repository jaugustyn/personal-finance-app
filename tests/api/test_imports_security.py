"""Security/contract tests for /imports upload validation.

Covers MAX_UPLOAD_BYTES (413), extension allowlist (415), MIME allowlist (415),
and empty-file handling (422). See _read_validated in apps/api/routers/imports.py.
"""
from __future__ import annotations

import io


def test_upload_rejects_oversize_payload(client) -> None:
    big = b"date;amount\n" + (b"2026-01-01;-1.00\n" * 700_000)  # > 10 MiB
    assert len(big) > 10 * 1024 * 1024
    r = client.post(
        "/imports",
        files={"file": ("big.csv", io.BytesIO(big), "text/csv")},
        data={"source": "pekao"},
    )
    assert r.status_code == 413


def test_upload_rejects_unknown_extension(client) -> None:
    r = client.post(
        "/imports",
        files={"file": ("payload.exe", io.BytesIO(b"hello"), "application/octet-stream")},
        data={"source": "pekao"},
    )
    assert r.status_code == 415


def test_upload_rejects_excel_until_parser_support_exists(client) -> None:
    r = client.post(
        "/imports",
        files={
            "file": (
                "payload.xlsx",
                io.BytesIO(b"not-really-excel"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"source": "generic"},
    )
    assert r.status_code == 415


def test_upload_rejects_unknown_mime(client) -> None:
    r = client.post(
        "/imports",
        files={"file": ("ok.csv", io.BytesIO(b"a;b\n1;2\n"), "image/png")},
        data={"source": "pekao"},
    )
    assert r.status_code == 415


def test_upload_rejects_empty_file(client) -> None:
    r = client.post(
        "/imports",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        data={"source": "pekao"},
    )
    assert r.status_code == 422
