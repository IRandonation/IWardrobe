"""Create explicit local demo accounts without embedding or printing passwords."""

import json
import secrets
from pathlib import Path

from sqlalchemy import select

from iwardrobe.config import ROOT
from iwardrobe.db import SessionLocal
from iwardrobe.identity import hasher
from iwardrobe.models import User
from iwardrobe.wardrobe import import_demo

destination = ROOT / ".local" / "demo-accounts.json"
destination.parent.mkdir(parents=True, exist_ok=True)
accounts = (
    json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else []
)
with SessionLocal() as db:
    for username, display_name in [("demo", "体验衣橱"), ("demo2", "第二个衣橱")]:
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            password = secrets.token_urlsafe(14)
            user = User(
                username=username,
                display_name=display_name,
                password_hash=hasher.hash(password),
            )
            db.add(user)
            db.commit()
            accounts.append({"username": username, "password": password})
        if username == "demo":
            count = import_demo(db, user)
            print(f"Seeded {count} synthetic garments for demo")
destination.write_text(
    json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    f"Local-only demo credentials saved to {destination}; existing passwords were not changed."
)
