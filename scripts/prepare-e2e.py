"""Create fresh, isolated browser-test accounts; never reuses demo or real accounts."""

import json
import secrets

from iwardrobe.config import ROOT
from iwardrobe.db import SessionLocal
from iwardrobe.identity import hasher
from iwardrobe.models import User

account_groups = {}
with SessionLocal() as db:
    for filename, prefix in [
        ("e2e-accounts.json", "e2e"),
        ("cutout-e2e-accounts.json", "e2e-cutout"),
    ]:
        accounts = {}
        for device in ["desktop", "mobile"]:
            username = f"{prefix}-{device}-{secrets.token_hex(4)}"
            password = secrets.token_urlsafe(18)
            db.add(
                User(
                    username=username,
                    display_name=f"{device} 测试衣橱",
                    password_hash=hasher.hash(password),
                )
            )
            accounts[device] = {"username": username, "password": password}
        account_groups[filename] = accounts
    db.commit()
for filename, accounts in account_groups.items():
    path = ROOT / ".local" / filename
    path.write_text(json.dumps(accounts), encoding="utf-8")
print("Created four isolated browser-test accounts. Credentials saved locally.")
