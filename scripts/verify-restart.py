"""Local Windows + WSL validation: briefly stops ONLY this project's recorded services."""
import hashlib
import json
import secrets
import subprocess
import time

import httpx

from iwardrobe.config import ROOT
from iwardrobe.db import SessionLocal, engine
from iwardrobe.identity import hasher
from iwardrobe.models import User
from iwardrobe.schemas import GarmentInput
from iwardrobe.wardrobe import create_garment


def powershell(script: str):
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / script)],
        cwd=ROOT,
        check=True,
    )


def dependency_script(script: str):
    linux_path = subprocess.check_output(
        ["wsl", "-d", "Ubuntu-22.04", "--", "wslpath", "-a", (ROOT / "scripts" / script).as_posix()],
        text=True,
    ).strip()
    subprocess.run(["wsl", "-d", "Ubuntu-22.04", "--", "bash", linux_path], check=True)


credentials = json.loads((ROOT / ".local/demo-accounts.json").read_text(encoding="utf-8"))[0]
with httpx.Client(base_url="http://127.0.0.1:18765", headers={"Origin": "http://127.0.0.1:5173"}, timeout=10) as browser:
    response = browser.post("/api/auth/login", json=credentials)
    response.raise_for_status()
    before = browser.get("/api/garments").json()
    hashes = {item["id"]: hashlib.sha256(browser.get(item["image_url"] + "?original=true").content).hexdigest() for item in before if item["image_url"]}
    powershell("stop-local.ps1")
    probe_password = secrets.token_urlsafe(18)
    probe_username = "restart-" + secrets.token_hex(4)
    with SessionLocal() as db:
        user = User(username=probe_username, display_name="重启验证专用", password_hash=hasher.hash(probe_password))
        db.add(user)
        db.commit()
        garment = create_garment(db, user, GarmentInput(name="暂停期间排队的样图"), (ROOT / "fixtures/demo/images/oat-knit.png").read_bytes())
        probe_id = garment.id
    engine.dispose()
    try:
        dependency_script("stop-wsl-deps.sh")
    finally:
        try:
            dependency_script("start-wsl-deps.sh")
        finally:
            powershell("start-local.ps1")
    assert browser.get("/api/auth/me").status_code == 200, "Existing login session was lost"
    after = browser.get("/api/garments").json()
    assert before == after, "Wardrobe records changed after restart"
    for item in after:
        if item["image_url"]:
            assert hashlib.sha256(browser.get(item["image_url"] + "?original=true").content).hexdigest() == hashes[item["id"]]
    response = browser.post("/api/auth/login", json={"username": probe_username, "password": probe_password})
    response.raise_for_status()
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        jobs = browser.get("/api/jobs").json()
        if jobs and all(job["status"] == "succeeded" for job in jobs):
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Queued thumbnail was not recovered by the restarted worker")
    assert browser.get(f"/api/garments/{probe_id}").json()["image_ready"] is True
    result = {"records_preserved": len(before), "original_sha256_preserved": len(hashes), "session_preserved": True, "queued_job_recovered": True, "services_restarted": ["api", "worker", "web", "postgresql", "redis"]}
    (ROOT / ".local/restart-validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
