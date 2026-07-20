"""Run privacy-safe, read-only checks against the configured database."""
from __future__ import annotations

from finance.db import SessionLocal
from finance.integrity import check_data_integrity


def main() -> int:
    with SessionLocal() as session:
        issues = check_data_integrity(session)
    if not issues:
        print("Data integrity: OK")
        return 0
    print("Data integrity: FAILED")
    for issue in issues:
        sample = ", ".join(str(value) for value in issue.sample_ids) or "none"
        print(f"- {issue.code}: {issue.count} (sample IDs: {sample})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
