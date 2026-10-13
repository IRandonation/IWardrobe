import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import LoginAttempt, LoginSession, User, now

hasher = PasswordHasher()
COOKIE = "iw_session"
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token: str) -> str:
    return hmac.new(token.encode(), b"iwardrobe:csrf:v1", hashlib.sha256).hexdigest()


def check_origin(request: Request) -> None:
    if request.headers.get("origin") not in settings().allowed_origins.split(","):
        raise HTTPException(403, "请求来源不受信任，请从应用页面重试")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE, "")
    session = db.get(LoginSession, token_hash(token))
    if not session or session.expires_at <= now():
        raise HTTPException(401, "请先登录")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "账号不可用")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf_for(token)):
            raise HTTPException(403, "页面会话已变更，请刷新后重试")
    return user


def login(db: Session, username: str, password: str, ip: str) -> tuple[User, str]:
    username = username.strip().lower()
    # PostgreSQL is also the limiter store, so restarting the API does not reset it.
    keys = sorted([token_hash("ip:" + ip), token_hash("account:" + username)])
    attempts = []
    for key in keys:
        db.execute(
            insert(LoginAttempt)
            .values(key=key, count=0, reset_at=now() + timedelta(minutes=15))
            .on_conflict_do_nothing()
        )
        attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
        if attempt.reset_at <= now():
            attempt.count = 0
            attempt.reset_at = now() + timedelta(minutes=15)
        if attempt.count >= 15:
            db.rollback()
            raise HTTPException(429, "尝试次数过多，请在 15 分钟后重试")
        attempts.append(attempt)
    user = db.scalar(select(User).where(User.username == username))
    valid = False
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, password)
    except VerificationError:
        pass
    if not valid or not user or not user.active:
        for attempt in attempts:
            attempt.count += 1
        db.commit()
        raise HTTPException(401, "账号或密码不正确")
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=now() + timedelta(hours=settings().session_hours),
        )
    )
    db.commit()
    return user, token
