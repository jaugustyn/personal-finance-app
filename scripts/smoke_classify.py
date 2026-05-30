from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)
CASES = [
    ("CARREFOUR KRAKOW", "", "-31.41", "2026-04-18"),
    ("ORLEN STACJA", "", "-150.00", "2026-04-01"),
    ("Apteka DOZ Florianska", "", "-89.00", "2026-04-10"),
    ("IKEA Krakow", "", "-1500", "2026-03-12"),
    ("Lokata 6M PLN", "", "-2000", "2026-02-01"),
    ("Multikino Bonarka", "", "-45", "2026-04-29"),
    ("Spotify Premium", "", "-26.99", "2026-04-15"),
]
for m, t, a, d in CASES:
    r = client.post(
        "/ml/classify",
        json={"merchant": m, "title": t, "amount": a, "booking_date": d},
    )
    cat = r.json().get("category")
    print(f"{m:35s} -> {cat}")
