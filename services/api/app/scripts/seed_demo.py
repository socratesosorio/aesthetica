#!/usr/bin/env python3
from __future__ import annotations

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.auth import get_or_create_user
from app.services.product_ingest import ingest_products_csv
from ml_core.config import CONFIG


def main() -> None:
    db = SessionLocal()
    try:
        user = get_or_create_user(db, settings.dev_auth_email, settings.dev_auth_password)
        count = ingest_products_csv(db, CONFIG.product_csv_path)
        print(f"seeded user={user.email} products={count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
