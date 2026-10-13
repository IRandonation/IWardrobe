from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .identity import COOKIE, check_origin, csrf_for, current_user, login, token_hash
from .media import file_path
from .models import Asset, Garment, Job, LoginSession, User, now, uid
from .schemas import (
    GarmentInput,
    GarmentOut,
    GarmentUpdate,
    ImportOut,
    JobOut,
    LoginInput,
    SessionOut,
    UserOut,
    VersionInput,
)
from .wardrobe import (
    create_garment,
    garment_output,
    import_demo,
    output,
    owned_garment,
    record_wear,
    update_garment,
)

app = FastAPI(
    title="IWardrobe", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json"
)
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(current_user)]


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/api/health")
def health(db: Db):
    db.execute(text("SELECT 1"))
    try:
        with Redis.from_url(
            settings().redis_url, socket_connect_timeout=1, socket_timeout=1
        ) as redis:
            queue = bool(redis.ping())
    except Exception:
        queue = False
    return {"database": "ok", "queue": "ok" if queue else "unavailable", "version": "0.1.0"}


@app.post("/api/auth/login", response_model=SessionOut)
def sign_in(payload: LoginInput, request: Request, response: Response, db: Db):
    check_origin(request)
    user, token = login(
        db, payload.username, payload.password, request.client.host if request.client else "local"
    )
    previous = db.get(LoginSession, token_hash(request.cookies.get(COOKIE, "")))
    if previous:
        db.delete(previous)
        db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        max_age=settings().session_hours * 3600,
        path="/api",
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_for(token))


@app.get("/api/auth/me", response_model=SessionOut)
def me(request: Request, user: Actor):
    return SessionOut(
        user=UserOut.model_validate(user), csrf_token=csrf_for(request.cookies[COOKIE])
    )


@app.post("/api/auth/logout", status_code=204)
def sign_out(request: Request, response: Response, user: Actor, db: Db):
    session = db.get(LoginSession, token_hash(request.cookies[COOKIE]))
    db.delete(session)
    db.commit()
    response.delete_cookie(
        COOKIE, path="/api", secure=settings().cookie_secure, httponly=True, samesite="lax"
    )


@app.get("/api/garments", response_model=list[GarmentOut])
def garments(user: Actor, db: Db):
    rows = db.execute(
        select(Garment, Asset)
        .outerjoin(Asset, (Asset.garment_id == Garment.id) & (Asset.user_id == Garment.user_id))
        .where(Garment.user_id == user.id)
        .order_by(Garment.created_at.desc())
    ).all()
    return [output(garment, asset) for garment, asset in rows]


@app.post("/api/garments", response_model=GarmentOut, status_code=201)
def add_garment(payload: GarmentInput, user: Actor, db: Db):
    return garment_output(db, create_garment(db, user, payload))


@app.post("/api/garments/upload", response_model=GarmentOut, status_code=201)
def upload_garment(user: Actor, db: Db, file: UploadFile = File(), name: str = Form("新衣物")):
    name = name.strip()
    if not name or len(name) > 100:
        raise HTTPException(422, "名称需要 1–100 个字符")
    data = file.file.read(settings().max_upload_bytes + 1)
    return garment_output(db, create_garment(db, user, GarmentInput(name=name), data))


@app.post("/api/demo/import", response_model=ImportOut)
def seed_demo(user: Actor, db: Db):
    count = import_demo(db, user)
    return ImportOut(
        imported=count,
        message=f"已导入 {count} 件 AI 生成的演示衣物"
        if count
        else "演示衣物已在衣橱中，不会重复导入",
    )


@app.get("/api/garments/{garment_id}", response_model=GarmentOut)
def detail(garment_id: str, user: Actor, db: Db):
    return garment_output(db, owned_garment(db, user.id, garment_id))


@app.patch("/api/garments/{garment_id}", response_model=GarmentOut)
def update(garment_id: str, payload: GarmentUpdate, user: Actor, db: Db):
    return garment_output(db, update_garment(db, user.id, garment_id, payload))


@app.post("/api/garments/{garment_id}/wear", response_model=GarmentOut)
def wear(garment_id: str, payload: VersionInput, user: Actor, db: Db):
    return garment_output(db, record_wear(db, user.id, garment_id, payload.expected_version))


@app.get("/api/assets/{asset_id}/image")
def image_file(asset_id: str, user: Actor, db: Db, original: bool = Query(False)):
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.user_id == user.id))
    if not asset:
        raise HTTPException(404, "图片不存在")
    key = asset.original_key if original or not asset.thumbnail_key else asset.thumbnail_key
    path = file_path(key)
    if not path.is_file():
        raise HTTPException(404, "图片文件不可用")
    return FileResponse(
        path, media_type=asset.content_type if key == asset.original_key else "image/webp"
    )


@app.get("/api/jobs", response_model=list[JobOut])
def jobs(user: Actor, db: Db):
    return db.scalars(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(100)
    ).all()


@app.post("/api/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: str, user: Actor, db: Db):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id).with_for_update())
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status != "failed":
        raise HTTPException(409, "仅失败任务可重试")
    job.status, job.error, job.lease_until = "queued", None, None
    job.dispatch_key = uid()
    job.attempts = 0
    job.updated_at = now()
    db.commit()
    return job
