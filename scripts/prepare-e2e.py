"""Create fresh, isolated browser-test accounts; never reuses demo or real accounts."""

import json
import secrets

from iwardrobe.config import ROOT
from iwardrobe.db import SessionLocal
from iwardrobe.identity import hasher
from iwardrobe.models import User

accounts = {}
with SessionLocal() as db:
    for device in ["desktop", "mobile"]:
        username = f"e2e-{device}-{secrets.token_hex(4)}"
        password = secrets.token_urlsafe(18)
        db.add(
            User(
                username=username,
                display_name=f"{device} 测试衣橱",
                password_hash=hasher.hash(password),
            )
        )
        accounts[device] = {"username": username, "password": password}
    db.commit()
path = ROOT / ".local/e2e-accounts.json"
path.write_text(json.dumps(accounts), encoding="utf-8")
print("Created two isolated browser-test accounts. Credentials saved locally.")
