import asyncio
from datetime import timedelta
from io import BytesIO

import pytest
from PIL import Image

from iwardrobe import jobs
from iwardrobe.db import SessionLocal
from iwardrobe.media import file_path
from iwardrobe.models import Asset, Job, User, now, uid

MODEL = "birefnet-general-lite"


def upload(client, data, model=None):
    fields = {"name": "真实照片抠图测试"}
    if model is not None:
        fields["cutout_model"] = model
    response = client.post(
        "/api/garments/upload",
        data=fields,
        files={"file": ("sample.png", data, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def enqueue(client, garment, model):
    response = client.post(f"/api/assets/{garment['asset_id']}/cutouts", json={"model": model})
    assert response.status_code == 202, response.text
    return response.json()


def dispatch(job_id):
    with SessionLocal() as db:
        return db.get(Job, job_id).dispatch_key


def process(job_id, dispatch_key=None):
    asyncio.run(jobs.process_cutout({}, job_id, dispatch_key or dispatch(job_id)))


def result(client, garment):
    response = client.get(f"/api/garments/{garment['id']}")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def inference(monkeypatch):
    calls = []

    async def run_cutout(original, target, model):
        # Real PNG output exercises storage and authenticated image delivery;
        # inference itself is tested separately against the downloaded models.
        output = BytesIO()
        Image.new("RGBA", (4, 4), (len(calls) * 30, 80, 120, 128)).save(output, "PNG")
        path = file_path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(output.getvalue())
        calls.append({"original": original, "target": target, "model": model})
        return {"duration_ms": 123, "model_version": "test-model-v1"}

    monkeypatch.setattr(jobs, "run_cutout", run_cutout)
    return calls


def test_cutout_keeps_original_and_allows_display_selection(authenticated, image_bytes, inference):
    garment = upload(authenticated, image_bytes)
    job = enqueue(authenticated, garment, MODEL)
    process(job["id"])

    current = result(authenticated, garment)
    assert len(current["cutouts"]) == 1
    cutout = current["cutouts"][0]
    assert cutout["model"] == MODEL
    assert authenticated.get(current["original_image_url"]).content == image_bytes
    assert cutout["duration_ms"] == 123
    assert cutout["model_version"] == "test-model-v1"
    image = authenticated.get(cutout["image_url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "no-store"
    assert Image.open(BytesIO(image.content)).mode == "RGBA"
    selected = authenticated.put(
        f"/api/assets/{garment['asset_id']}/display", json={"model": MODEL}
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["display_model"] == MODEL
    assert authenticated.get(selected.json()["image_url"]).content == image.content

    restored = authenticated.put(f"/api/assets/{garment['asset_id']}/display", json={"model": None})
    assert restored.status_code == 200
    assert restored.json()["display_model"] is None
    assert authenticated.get(restored.json()["image_url"]).content == image_bytes
    assert authenticated.get(restored.json()["original_image_url"]).content == image_bytes
    assert len(inference) == 1


def test_latest_success_is_available_while_a_new_attempt_fails(
    authenticated, image_bytes, inference, monkeypatch
):
    garment = upload(authenticated, image_bytes)
    for _ in range(2):
        latest = enqueue(authenticated, garment, MODEL)
        process(latest["id"])
    assert [item["job_id"] for item in result(authenticated, garment)["cutouts"]] == [latest["id"]]

    async def fail(*args):
        raise RuntimeError("simulated inference failure")

    monkeypatch.setattr(jobs, "run_cutout", fail)
    failed = enqueue(authenticated, garment, MODEL)
    process(failed["id"])
    assert [item["job_id"] for item in result(authenticated, garment)["cutouts"]] == [latest["id"]]


def test_cutout_creation_selection_and_images_are_owned(authenticated, bob, image_bytes, inference):
    garment = upload(authenticated, image_bytes)
    job = enqueue(authenticated, garment, MODEL)
    process(job["id"])
    current = result(authenticated, garment)
    assert (
        bob.post(f"/api/assets/{garment['asset_id']}/cutouts", json={"model": MODEL}).status_code
        == 404
    )
    assert (
        bob.put(f"/api/assets/{garment['asset_id']}/display", json={"model": MODEL}).status_code
        == 404
    )
    assert bob.get(current["cutouts"][0]["image_url"]).status_code == 404
    assert bob.get(current["original_image_url"]).status_code == 404
    assert bob.post(f"/api/jobs/{job['id']}/retry").status_code == 404
    other = upload(authenticated, image_bytes)
    assert (
        authenticated.get(f"/api/assets/{other['asset_id']}/image?cutout={job['id']}").status_code
        == 404
    )


@pytest.mark.parametrize("invalid_model", ["unknown-model", "u2netp"])
def test_invalid_models_and_unavailable_display_are_rejected(
    authenticated, image_bytes, invalid_model
):
    garment = upload(authenticated, image_bytes)
    for endpoint in ("cutouts", "display"):
        method = authenticated.post if endpoint == "cutouts" else authenticated.put
        response = method(
            f"/api/assets/{garment['asset_id']}/{endpoint}", json={"model": invalid_model}
        )
        assert response.status_code == 422
    assert (
        authenticated.put(
            f"/api/assets/{garment['asset_id']}/display", json={"model": MODEL}
        ).status_code
        == 409
    )
    invalid = authenticated.post(
        "/api/garments/upload",
        data={"name": "无效模型", "cutout_model": invalid_model},
        files={"file": ("sample.png", image_bytes, "image/png")},
    )
    assert invalid.status_code == 422
    assert len(authenticated.get("/api/garments").json()) == 1


@pytest.mark.parametrize("model", [None, MODEL])
def test_upload_schedules_only_requested_cutout(authenticated, image_bytes, model):
    garment = upload(authenticated, image_bytes, model)
    pending = authenticated.get("/api/jobs").json()
    assert [job["kind"] for job in pending].count("thumbnail") == 1
    cutouts = [job for job in pending if job["kind"] == "cutout"]
    assert len(cutouts) == (1 if model else 0)
    if model:
        assert cutouts[0]["model"] == model
        assert cutouts[0]["asset_id"] == garment["asset_id"]


def test_duplicate_model_is_rejected_while_queued_and_running(
    authenticated, image_bytes, inference, monkeypatch
):
    garment = upload(authenticated, image_bytes)
    first = enqueue(authenticated, garment, MODEL)
    endpoint = f"/api/assets/{garment['asset_id']}/cutouts"
    assert authenticated.post(endpoint, json={"model": MODEL}).status_code == 409
    original = jobs.run_cutout

    async def run_while_checking_duplicate(*args):
        assert authenticated.post(endpoint, json={"model": MODEL}).status_code == 409
        return await original(*args)

    monkeypatch.setattr(jobs, "run_cutout", run_while_checking_duplicate)
    process(first["id"])
    assert len(inference) == 1


def test_failure_retry_preserves_original_and_rejects_old_dispatch(
    authenticated, image_bytes, inference, monkeypatch
):
    garment = upload(authenticated, image_bytes)
    job = enqueue(authenticated, garment, MODEL)
    old_dispatch = dispatch(job["id"])
    original = jobs.run_cutout

    async def fail(*args):
        raise RuntimeError("simulated inference failure")

    monkeypatch.setattr(jobs, "run_cutout", fail)
    process(job["id"])
    with SessionLocal() as db:
        failed = db.get(Job, job["id"])
        assert failed.status == "failed"
        assert failed.output_key is None
    assert result(authenticated, garment)["cutouts"] == []
    assert authenticated.get(garment["original_image_url"]).content == image_bytes
    retry = authenticated.post(f"/api/jobs/{job['id']}/retry")
    assert retry.status_code == 200 and retry.json()["status"] == "queued"
    assert dispatch(job["id"]) != old_dispatch
    monkeypatch.setattr(jobs, "run_cutout", original)
    process(job["id"], old_dispatch)
    assert inference == []
    process(job["id"])
    process(job["id"])
    assert len(inference) == 1
    assert result(authenticated, garment)["cutouts"][0]["job_id"] == job["id"]


def test_dispatch_changed_during_inference_cannot_publish(
    authenticated, image_bytes, inference, monkeypatch
):
    garment = upload(authenticated, image_bytes)
    job = enqueue(authenticated, garment, MODEL)
    original = jobs.run_cutout

    async def replace_dispatch(*args):
        output = await original(*args)
        with SessionLocal() as db:
            expired = db.get(Job, job["id"])
            expired.status = "queued"
            expired.dispatch_key = uid()
            expired.lease_until = None
            db.commit()
        return output

    monkeypatch.setattr(jobs, "run_cutout", replace_dispatch)
    process(job["id"])
    with SessionLocal() as db:
        invalidated = db.get(Job, job["id"])
        assert invalidated.status == "queued"
        assert invalidated.output_key is None
    assert result(authenticated, garment)["cutouts"] == []
    assert not file_path(inference[0]["target"]).exists()


@pytest.mark.parametrize("disable_during_inference", [False, True])
def test_disabled_account_cannot_publish_cutout(
    authenticated, image_bytes, inference, monkeypatch, disable_during_inference
):
    garment = upload(authenticated, image_bytes)
    job = enqueue(authenticated, garment, MODEL)

    def disable():
        with SessionLocal() as db:
            user = db.get(User, db.get(Job, job["id"]).user_id)
            user.active = False
            db.commit()

    if disable_during_inference:
        original = jobs.run_cutout

        async def disable_after_inference(*args):
            output = await original(*args)
            disable()
            return output

        monkeypatch.setattr(jobs, "run_cutout", disable_after_inference)
    else:
        disable()
    process(job["id"])
    with SessionLocal() as db:
        finished = db.get(Job, job["id"])
        assert finished.status == "failed"
        assert finished.output_key is None
        assert db.get(Asset, garment["asset_id"]).display_model is None
    assert len(inference) == int(disable_during_inference)
    for call in inference:
        assert not file_path(call["target"]).exists()


def test_reconcile_routes_kinds_and_requeues_expired_cutout(authenticated, image_bytes):
    garment = upload(authenticated, image_bytes)
    cutout = enqueue(authenticated, garment, MODEL)
    old_dispatch = dispatch(cutout["id"])
    with SessionLocal() as db:
        expired = db.get(Job, cutout["id"])
        expired.status = "running"
        expired.attempts = 1
        expired.lease_until = now() - timedelta(seconds=1)
        db.commit()

    class Queue:
        def __init__(self):
            self.calls = []

        async def enqueue_job(self, function, job_id, dispatch_key, **kwargs):
            self.calls.append((function, job_id, dispatch_key, kwargs["_job_id"]))

    queue = Queue()
    asyncio.run(jobs.reconcile({"redis": queue}))
    assert {call[0] for call in queue.calls} == {"process_thumbnail", "process_cutout"}
    assert len(queue.calls) == 2
    with SessionLocal() as db:
        recovered = db.get(Job, cutout["id"])
        assert recovered.status == "queued"
        assert recovered.dispatch_key != old_dispatch
        assert ("process_cutout", recovered.id, recovered.dispatch_key, recovered.dispatch_key) in (
            queue.calls
        )


def test_historical_result_remains_readable_without_becoming_a_display_option(
    authenticated, bob, image_bytes
):
    garment = upload(authenticated, image_bytes)
    with SessionLocal() as db:
        asset = db.get(Asset, garment["asset_id"])
        historical_id = uid()
        key = f"{asset.user_id}/{asset.id}/cutout-historical.png"
        path = file_path(key)
        Image.new("RGBA", (4, 4), (80, 120, 160, 128)).save(path, "PNG")
        db.add(
            Job(
                id=historical_id,
                user_id=asset.user_id,
                asset_id=asset.id,
                kind="cutout",
                model="u2netp",
                status="succeeded",
                output_key=key,
                duration_ms=123,
                model_version="historical-u2netp",
            )
        )
        asset.display_model = "u2netp"
        db.commit()

    history = authenticated.get("/api/jobs")
    assert history.status_code == 200
    old_job = next(job for job in history.json() if job["id"] == historical_id)
    assert old_job["model"] == "u2netp"
    assert old_job["status"] == "succeeded"
    listed = authenticated.get("/api/garments")
    assert listed.status_code == 200
    current = result(authenticated, garment)
    assert listed.json()[0]["display_model"] is None
    assert current["display_model"] is None
    assert current["cutouts"] == []
    assert authenticated.get(current["image_url"]).content == image_bytes
    historical_url = f"/api/assets/{garment['asset_id']}/image?cutout={historical_id}"
    image = authenticated.get(historical_url)
    assert image.status_code == 200 and image.content == path.read_bytes()
    assert bob.get(historical_url).status_code == 404


def test_retired_model_cannot_retry_or_run_inference(authenticated, image_bytes, inference):
    garment = upload(authenticated, image_bytes)
    with SessionLocal() as db:
        asset = db.get(Asset, garment["asset_id"])
        failed_id, queued_id = uid(), uid()
        for job_id, status in ((failed_id, "failed"), (queued_id, "queued")):
            db.add(
                Job(
                    id=job_id,
                    user_id=asset.user_id,
                    asset_id=asset.id,
                    kind="cutout",
                    model="u2netp",
                    status=status,
                )
            )
        db.commit()

    assert authenticated.post(f"/api/jobs/{failed_id}/retry").status_code == 422
    process(queued_id)
    assert inference == []
    with SessionLocal() as db:
        for job_id in (failed_id, queued_id):
            job = db.get(Job, job_id)
            assert job.status == "failed"
            assert job.output_key is None
        assert db.get(Job, queued_id).error
