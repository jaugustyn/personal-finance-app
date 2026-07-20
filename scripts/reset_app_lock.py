"""Disable the optional application lock for the local profile."""
from finance.db import SessionLocal
from finance.profile.service import get_or_create_profile
from finance.security.app_lock import DEFAULT_TIMEOUT_MINUTES


def main() -> None:
    with SessionLocal() as session:
        profile = get_or_create_profile(session)
        profile.app_lock_secret_hash = None
        profile.app_lock_timeout_minutes = DEFAULT_TIMEOUT_MINUTES
        session.commit()
    print("Application lock disabled. Restart the API if it is currently running.")


if __name__ == "__main__":
    main()
