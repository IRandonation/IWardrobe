import asyncio
import logging
from datetime import timedelta

from arq import cron, func
from arq.connections import RedisSettings
from sqlalchemy import or_, select

from .config import settings
from .db import SessionLocal
from .image_processing import MODELS, run_cutout
from .media import file_path, thumbnail
from .models import Asset, Job, User, now, uid

log = logging.getLogger(__name__)


async def reconcile(ctx: dict) -> None:
    with SessionLocal() as db:
        jobs = db.scalars(
            select(Job)
            .where(
                or_(Job.status == "queued", (Job.status == "running") & (Job.lease_until < now()))
            )
            .order_by(Job.created_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        ).all()
        pending = []
        for job in jobs:
            if job.kind not in ("thumbnail", "cutout"):
                job.status = "failed"
                job.error = "不支持的图片任务类型"
                job.updated_at = now()
                continue
            if job.kind == "cutout" and job.model not in MODELS:
                job.status = "failed"
                job.error = "该模型已停用，请在衣物详情中使用 BiRefNet Lite 重新抠图"
                job.lease_until = None
                job.updated_at = now()
                continue
            if job.status == "running":
                job.status = "queued" if job.attempts < 3 else "failed"
                job.error = "处理进程中断，请重试" if job.status == "failed" else None
                job.dispatch_key = uid()
                job.lease_until = None
                job.updated_at = now()
            if job.status == "queued":
                pending.append((job.kind, job.id, job.dispatch_key))
        db.commit()
    for kind, job_id, dispatch_key in pending:
        await ctx["redis"].enqueue_job(
            f"process_{kind}", job_id, dispatch_key, _job_id=dispatch_key
        )


async def process_thumbnail(ctx: dict, job_id: str, dispatch_key: str) -> None:
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if (
            not job
            or job.kind != "thumbnail"
            or job.dispatch_key != dispatch_key
            or job.status != "queued"
        ):
            return
        user = db.get(User, job.user_id)
        asset = db.scalar(
            select(Asset).where(Asset.id == job.asset_id, Asset.user_id == job.user_id)
        )
        if not user or not user.active or not asset:
            job.status = "failed"
            job.error = "账号或原图不可用"
            db.commit()
            return
        job.status = "running"
        job.attempts += 1
        job.lease_until = now() + timedelta(seconds=90)
        job.updated_at = now()
        original = asset.original_key
        target = f"{job.user_id}/{asset.id}/thumbnail-{dispatch_key}.webp"
        db.commit()
    try:
        await asyncio.to_thread(thumbnail, original, target)
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if not job or job.dispatch_key != dispatch_key or job.status != "running":
                file_path(target).unlink(missing_ok=True)
                return
            user = db.get(User, job.user_id)
            if not user or not user.active:
                file_path(target).unlink(missing_ok=True)
                job.status = "failed"
                job.error = "账号不可用"
            else:
                asset = db.scalar(
                    select(Asset).where(Asset.id == job.asset_id, Asset.user_id == job.user_id)
                )
                if not asset:
                    file_path(target).unlink(missing_ok=True)
                    job.status = "failed"
                    job.error = "原图不可用"
                else:
                    asset.thumbnail_key = target
                    job.status = "succeeded"
                    job.error = None
            job.lease_until = None
            job.updated_at = now()
            db.commit()
    except Exception:
        log.exception("Thumbnail job failed: %s", job_id)
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job and job.dispatch_key == dispatch_key and job.status == "running":
                job.status = "failed"
                job.lease_until = None
                job.error = "缩略图处理失败，原图仍保留，可重试"
                job.updated_at = now()
                db.commit()


def fail_cutout(job_id: str, dispatch_key: str) -> None:
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job and job.dispatch_key == dispatch_key and job.status == "running":
            job.status = "failed"
            job.lease_until = None
            job.error = "抠图处理失败，原图和之前的成功结果仍保留，可重试"
            job.output_key, job.duration_ms, job.model_version = None, None, None
            job.updated_at = now()
            db.commit()


async def process_cutout(ctx: dict, job_id: str, dispatch_key: str) -> None:
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if (
            not job
            or job.kind != "cutout"
            or job.dispatch_key != dispatch_key
            or job.status != "queued"
        ):
            return
        if job.model not in MODELS:
            job.status = "failed"
            job.error = "该模型已停用，请在衣物详情中使用 BiRefNet Lite 重新抠图"
            job.lease_until = None
            job.updated_at = now()
            db.commit()
            return
        user = db.get(User, job.user_id)
        asset = db.scalar(
            select(Asset).where(Asset.id == job.asset_id, Asset.user_id == job.user_id)
        )
        if not user or not user.active or not asset:
            job.status = "failed"
            job.error = "账号或原图不可用"
            job.updated_at = now()
            db.commit()
            return
        job.status = "running"
        job.attempts += 1
        job.lease_until = now() + timedelta(seconds=720)
        job.updated_at = now()
        original, model = asset.original_key, job.model
        target = f"{job.user_id}/{asset.id}/cutout-{job.id}-{dispatch_key}.png"
        db.commit()
    try:
        result = await run_cutout(original, target, model)
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if not job or job.dispatch_key != dispatch_key or job.status != "running":
                file_path(target).unlink(missing_ok=True)
                return
            user = db.get(User, job.user_id)
            asset = db.scalar(
                select(Asset).where(Asset.id == job.asset_id, Asset.user_id == job.user_id)
            )
            if not user or not user.active or not asset:
                file_path(target).unlink(missing_ok=True)
                job.status = "failed"
                job.error = "账号或原图不可用"
            else:
                job.output_key = target
                job.duration_ms = result["duration_ms"]
                job.model_version = result["model_version"]
                job.status = "succeeded"
                job.error = None
            job.lease_until = None
            job.updated_at = now()
            db.commit()
    except asyncio.CancelledError:
        file_path(target).unlink(missing_ok=True)
        fail_cutout(job_id, dispatch_key)
        raise
    except Exception:
        log.exception("Cutout job failed: %s", job_id)
        file_path(target).unlink(missing_ok=True)
        fail_cutout(job_id, dispatch_key)


class WorkerSettings:
    functions = (process_thumbnail, func(process_cutout, timeout=660))
    cron_jobs = (cron(reconcile, second=set(range(0, 60, 10)), run_at_startup=True),)
    redis_settings = RedisSettings.from_dsn(settings().redis_url)
    max_jobs = 1
    job_timeout = 60
    keep_result = 15
    retry_jobs = False
