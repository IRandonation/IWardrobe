import asyncio
from datetime import timedelta

from arq.connections import RedisSettings, create_pool
from sqlalchemy import select

from iwardrobe.config import settings
from iwardrobe.db import SessionLocal
from iwardrobe.jobs import process_thumbnail, reconcile
from iwardrobe.media import file_path
from iwardrobe.models import Asset, Garment, Job, User, now


def upload(client, data):
    response = client.post(
        "/api/garments/upload",
        data={"name": "测试针织衫"},
        files={"file": ("sample.png", data, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def fields(garment, **changes):
    return {
        **{
            k: garment[k]
            for k in [
                "name",
                "category",
                "color",
                "season",
                "material",
                "care",
                "notes",
                "status",
                "favorite",
            ]
        },
        "expected_version": garment["version"],
        **changes,
    }


def test_independent_accounts_cover_images_jobs_and_mutations(authenticated, bob, image_bytes):
    garment = upload(authenticated, image_bytes)
    job = authenticated.get("/api/jobs").json()[0]
    assert len(authenticated.get("/api/garments").json()) == 1
    assert bob.get("/api/garments").json() == []
    assert bob.get("/api/jobs").json() == []
    assert bob.get(f"/api/garments/{garment['id']}").status_code == 404
    assert bob.get(garment["image_url"]).status_code == 404
    assert (
        bob.patch(
            f"/api/garments/{garment['id']}", json=fields(garment, name="越权修改")
        ).status_code
        == 404
    )
    assert bob.post(f"/api/jobs/{job['id']}/retry").status_code == 404
    assert (
        bob.post(f"/api/garments/{garment['id']}/wear", json={"expected_version": 1}).status_code
        == 404
    )


def test_upload_thumbnail_state_changes_and_optimistic_lock(authenticated, image_bytes):
    garment = upload(authenticated, image_bytes)
    with SessionLocal() as db:
        job = db.scalar(select(Job))
        job_id, dispatch_key = job.id, job.dispatch_key
    asyncio.run(process_thumbnail({}, job_id, dispatch_key))
    asyncio.run(process_thumbnail({}, job_id, dispatch_key))
    image = authenticated.get(garment["image_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/webp"
    assert image.headers["cache-control"] == "no-store"
    assert authenticated.get("/api/jobs").json()[0]["attempts"] == 1
    result = authenticated.patch(
        f"/api/garments/{garment['id']}", json=fields(garment, status="laundry")
    )
    assert result.status_code == 200
    assert (
        authenticated.patch(
            f"/api/garments/{garment['id']}", json=fields(garment, name="旧页面")
        ).status_code
        == 409
    )
    dirty = result.json()
    assert (
        authenticated.post(
            f"/api/garments/{garment['id']}/wear", json={"expected_version": dirty["version"]}
        ).status_code
        == 409
    )
    clean = authenticated.patch(
        f"/api/garments/{garment['id']}", json=fields(dirty, status="available")
    ).json()
    worn = authenticated.post(
        f"/api/garments/{garment['id']}/wear", json={"expected_version": clean["version"]}
    )
    assert worn.status_code == 200 and worn.json()["wear_count"] == 1
    assert (
        authenticated.post(
            f"/api/garments/{garment['id']}/wear", json={"expected_version": clean["version"]}
        ).status_code
        == 409
    )


def test_csrf_origin_and_logout(authenticated):
    assert (
        authenticated.post(
            "/api/garments", json={"name": "测试"}, headers={"X-CSRF-Token": "bad"}
        ).status_code
        == 403
    )
    assert (
        authenticated.post(
            "/api/garments", json={"name": "测试"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    cookie = authenticated.cookies.get("iw_session")
    assert authenticated.post("/api/auth/logout").status_code == 204
    authenticated.cookies.set("iw_session", cookie, path="/api")
    assert authenticated.get("/api/garments").status_code == 401


def test_invalid_media_cannot_create_partial_records(authenticated):
    response = authenticated.post(
        "/api/garments/upload",
        data={"name": "伪装图片"},
        files={"file": ("attack.png", b'<svg onload="alert(1)"/>', "image/png")},
    )
    assert response.status_code == 415
    assert authenticated.get("/api/garments").json() == []
    assert authenticated.get("/api/jobs").json() == []


def test_demo_seed_is_idempotent_and_private(authenticated, bob):
    assert authenticated.post("/api/demo/import").json()["imported"] == 4
    assert authenticated.post("/api/demo/import").json()["imported"] == 0
    assert len(authenticated.get("/api/garments").json()) == 4
    assert all(g["is_demo"] for g in authenticated.get("/api/garments").json())
    assert bob.get("/api/garments").json() == []
    assert bob.post("/api/demo/import").json()["imported"] == 4
    assert {g["id"] for g in bob.get("/api/garments").json()}.isdisjoint(
        {g["id"] for g in authenticated.get("/api/garments").json()}
    )


def test_failure_retry_keeps_original_and_completes(authenticated, image_bytes):
    garment = upload(authenticated, image_bytes)
    with SessionLocal() as db:
        job = db.scalar(select(Job))
        asset = db.get(Asset, job.asset_id)
        path = file_path(asset.original_key)
        job_id, dispatch_key = job.id, job.dispatch_key
    path.unlink()
    asyncio.run(process_thumbnail({}, job_id, dispatch_key))
    assert authenticated.get("/api/jobs").json()[0]["status"] == "failed"
    path.write_bytes(image_bytes)
    retry = authenticated.post(f"/api/jobs/{job_id}/retry")
    assert retry.status_code == 200 and retry.json()["status"] == "queued"
    with SessionLocal() as db:
        new_key = db.get(Job, job_id).dispatch_key
    asyncio.run(process_thumbnail({}, job_id, dispatch_key))
    assert authenticated.get("/api/jobs").json()[0]["status"] == "queued"
    asyncio.run(process_thumbnail({}, job_id, new_key))
    assert authenticated.get("/api/jobs").json()[0]["status"] == "succeeded"
    assert authenticated.get(garment["image_url"] + "?original=true").content == image_bytes


def test_expired_lease_is_requeued_in_real_redis(authenticated, image_bytes):
    upload(authenticated, image_bytes)
    with SessionLocal() as db:
        job = db.scalar(select(Job))
        job.status, job.attempts, job.lease_until = "running", 1, now() - timedelta(seconds=1)
        old_key, job_id = job.dispatch_key, job.id
        db.commit()

    async def recover():
        redis = await create_pool(RedisSettings.from_dsn(settings().redis_url))
        await reconcile({"redis": redis})
        with SessionLocal() as db:
            recovered = db.get(Job, job_id)
            assert recovered.dispatch_key != old_key
            assert recovered.status == "queued"
            assert await redis.exists(f"arq:job:{recovered.dispatch_key}")
            await redis.delete(f"arq:job:{recovered.dispatch_key}")
            await redis.zrem("arq:queue", recovered.dispatch_key)
        await redis.aclose()

    asyncio.run(recover())


def test_disabled_account_cannot_publish_job(authenticated, image_bytes):
    upload(authenticated, image_bytes)
    with SessionLocal() as db:
        job = db.scalar(select(Job))
        user = db.get(User, job.user_id)
        user.active = False
        job_id, dispatch_key = job.id, job.dispatch_key
        db.commit()
    asyncio.run(process_thumbnail({}, job_id, dispatch_key))
    with SessionLocal() as db:
        assert db.get(Job, job_id).status == "failed"
        assert db.scalar(select(Asset)).thumbnail_key is None
    assert authenticated.get("/api/garments").status_code == 401


def test_validation_and_login_failure(client):
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": "incorrect"}
        ).status_code
        == 401
    )
    assert client.get("/api/garments").status_code == 401


def test_database_rejects_cross_user_asset(authenticated, bob, image_bytes):
    from sqlalchemy.exc import IntegrityError
    import pytest

    garment = upload(authenticated, image_bytes)
    with SessionLocal() as db:
        other = db.scalar(select(User).where(User.username == "bob"))
        asset = db.scalar(select(Asset).where(Asset.garment_id == garment["id"]))
        asset.user_id = other.id
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
