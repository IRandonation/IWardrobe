import argparse
import getpass

from sqlalchemy import select

from .db import SessionLocal
from .identity import hasher
from .models import User
from .wardrobe import import_demo


def main():
    parser = argparse.ArgumentParser(description="IWardrobe local account maintenance")
    parser.add_argument("command", choices=["create-user", "seed-demo"])
    parser.add_argument("username")
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    username = args.username.strip().lower()
    if not username or len(username) > 80:
        parser.error("username must contain 1–80 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if args.command == "create-user":
            if user:
                parser.error("account already exists; no changes made")
            password = getpass.getpass("Password (at least 12 characters): ")
            if len(password) < 12 or len(password) > 200:
                parser.error("password must contain 12–200 characters")
            user = User(
                username=username,
                display_name=args.name or username,
                password_hash=hasher.hash(password),
            )
            db.add(user)
            db.commit()
            print(f"Created account: {username}")
        else:
            if not user:
                parser.error("account not found")
            print(f"Imported {import_demo(db, user)} synthetic demo garments")


if __name__ == "__main__":
    main()
