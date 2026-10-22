import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import ROOT
from .image_processing import MODELS
from .media import inspect_image, write_original
from .models import Asset, Garment, Job, User, WearRecord, now, uid
from .schemas import CutoutModel, CutoutOut, GarmentInput, GarmentOut, GarmentUpdate


def owned_garment(db: Session, user_id: str, garment_id: str, lock: bool = False) -> Garment:
    query = select(Garment).where(Garment.id == garment_id, Garment.user_id == user_id)
    garment = db.scalar(query.with_for_update() if lock else query)
    if not garment:
        raise HTTPException(404, "衣物不存在")
    return garment


def latest_cutouts(db: Session, user_id: str, asset_ids: list[str]) -> dict[str, list[Job]]:
    if not asset_ids:
        return {}
    ranked = (
        select(
            Job.id,
            func.row_number()
            .over(
                partition_by=(Job.asset_id, Job.model),
                order_by=(Job.updated_at.desc(), Job.id.desc()),
            )
            .label("position"),
        )
        .where(
            Job.user_id == user_id,
            Job.asset_id.in_(asset_ids),
            Job.kind == "cutout",
            Job.model.in_(MODELS),
            Job.status == "succeeded",
            Job.output_key.is_not(None),
        )
        .subquery()
    )
    jobs = db.scalars(
        select(Job).join(ranked, Job.id == ranked.c.id).where(ranked.c.position == 1)
    ).all()
    results: dict[str, list[Job]] = {}
    for job in jobs:
        results.setdefault(job.asset_id, []).append(job)
    return results


def output(garment: Garment, asset: Asset | None, cutouts: list[Job] | None = None) -> GarmentOut:
    results = [
        CutoutOut(
            model=job.model,
            job_id=job.id,
            image_url=f"/api/assets/{job.asset_id}/image?cutout={job.id}",
            duration_ms=job.duration_ms,
            model_version=job.model_version,
            created_at=job.created_at,
        )
        for job in cutouts or []
    ]
    selected = next(
        (result for result in results if asset and result.model == asset.display_model), None
    )
    return GarmentOut(
        **{field: getattr(garment, field) for field in GarmentInput.model_fields},
        id=garment.id,
        status=garment.status,
        favorite=garment.favorite,
        version=garment.version,
        wear_count=garment.wear_count,
        is_demo=garment.demo_key is not None,
        asset_id=asset.id if asset else None,
        image_url=selected.image_url
        if selected
        else f"/api/assets/{asset.id}/image"
        if asset
        else None,
        original_image_url=f"/api/assets/{asset.id}/image?original=true" if asset else None,
        display_model=selected.model if selected else None,
        cutouts=results,
        image_ready=bool(selected or (asset and asset.thumbnail_key)),
        created_at=garment.created_at,
        updated_at=garment.updated_at,
    )


def garment_output(db: Session, garment: Garment) -> GarmentOut:
    asset = db.scalar(
        select(Asset).where(Asset.garment_id == garment.id, Asset.user_id == garment.user_id)
    )
    cutouts = latest_cutouts(db, garment.user_id, [asset.id]).get(asset.id, []) if asset else []
    return output(garment, asset, cutouts)


def create_garment(
    db: Session,
    user: User,
    fields: GarmentInput,
    data: bytes | None = None,
    demo_key: str | None = None,
    cutout_model: CutoutModel | None = None,
) -> Garment:
    garment = Garment(id=uid(), user_id=user.id, **fields.model_dump(), demo_key=demo_key)
    asset = None
    job = None
    written = None
    try:
        if data is not None:
            ext, mime, width, height = inspect_image(data)
            asset_id = uid()
            key = f"{user.id}/{asset_id}/original.{ext}"
            written = write_original(key, data)
            asset = Asset(
                id=asset_id,
                user_id=user.id,
                garment_id=garment.id,
                original_key=key,
                content_type=mime,
                width=width,
                height=height,
            )
            job = Job(user_id=user.id, asset_id=asset_id)
        db.add(garment)
        db.flush()
        if asset:
            db.add(asset)
            db.flush()
            db.add(job)
            if cutout_model:
                db.add(Job(user_id=user.id, asset_id=asset.id, kind="cutout", model=cutout_model))
        db.commit()
    except Exception:
        db.rollback()
        if written:
            written.unlink(missing_ok=True)
        raise
    return garment


def update_garment(db: Session, user_id: str, garment_id: str, fields: GarmentUpdate) -> Garment:
    garment = owned_garment(db, user_id, garment_id, lock=True)
    check_version(garment, fields.expected_version)
    for key, value in fields.model_dump(exclude={"expected_version"}).items():
        setattr(garment, key, value)
    garment.version += 1
    garment.updated_at = now()
    db.commit()
    return garment


def check_version(garment: Garment, expected: int) -> None:
    if garment.version != expected:
        raise HTTPException(409, "衣物已在其他页面修改，请关闭后重新打开再编辑")


def record_wear(db: Session, user_id: str, garment_id: str, expected: int) -> Garment:
    garment = owned_garment(db, user_id, garment_id, lock=True)
    check_version(garment, expected)
    if garment.status != "available":
        raise HTTPException(409, "只有可穿衣物可以记录穿着，请先洗净或恢复衣物")
    db.add(WearRecord(user_id=user_id, garment_id=garment_id))
    garment.wear_count += 1
    garment.version += 1
    garment.updated_at = now()
    db.commit()
    return garment


def import_demo(db: Session, user: User) -> int:
    # Serialize imports for this account; unique(user_id,demo_key) also guards duplicate seeds.
    # Each item commits independently, allowing an interrupted import to resume safely.
    count = 0
    manifest = json.loads((ROOT / "fixtures/demo/manifest.json").read_text(encoding="utf-8"))
    for item in manifest:
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        existing = db.scalar(
            select(Garment.id).where(Garment.user_id == user.id, Garment.demo_key == item["key"])
        )
        if existing:
            db.commit()
            continue
        data = (ROOT / "fixtures/demo/images" / item["file"]).read_bytes()
        create_garment(db, user, GarmentInput(**item["fields"]), data, item["key"])
        count += 1
    return count
