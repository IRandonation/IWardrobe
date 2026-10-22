"""CPU cutouts in a terminable child process, isolated from the web/queue event loop."""

import asyncio
import json
import os
import subprocess
import sys
from importlib.metadata import version
from time import perf_counter

from .config import settings
from .media import file_path

MODELS = ("birefnet-general-lite",)
TIMEOUT_SECONDS = 600


async def stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        if os.name == "nt":
            # Windows venv python.exe launches the real interpreter as a child.
            # Killing only the launcher would leave ONNX computing in that child.
            killer = await asyncio.create_subprocess_exec(
                os.path.join(os.environ["SystemRoot"], "System32", "taskkill.exe"),
                "/PID", str(process.pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            await killer.wait()
        else:
            process.kill()
    await process.wait()


async def run_cutout(original: str, target: str, model: str) -> dict:
    if model not in MODELS:
        raise ValueError("Unsupported cutout model")
    # A timed-out thread keeps computing. A child process can actually be stopped,
    # and releases the larger model's memory before the next queue task starts.
    environment = os.environ.copy()
    environment["U2NET_HOME"] = str(settings().model_cache_dir.resolve())
    environment["OMP_NUM_THREADS"] = str(max(1, settings().cutout_threads))
    environment["NUMBA_NUM_THREADS"] = environment["OMP_NUM_THREADS"]
    # We request only the segmentation mask; optional PyMatting JIT is unused.
    environment["NUMBA_DISABLE_JIT"] = "1"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "iwardrobe.image_processing",
        original,
        target,
        model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), TIMEOUT_SECONDS)
        if process.returncode:
            raise RuntimeError(stderr.decode("utf-8", errors="replace")[-3000:])
        return json.loads(stdout)
    except BaseException:
        await stop_process(process)
        file_path(target).unlink(missing_ok=True)
        raise
    finally:
        file_path(target).with_suffix(".tmp").unlink(missing_ok=True)


def create_cutout(original: str, target: str, model: str) -> dict:
    started = perf_counter()
    from PIL import Image, ImageChops, ImageOps
    from rembg import new_session, remove

    if model not in MODELS:
        raise ValueError("Unsupported cutout model")
    session = new_session(model, providers=["CPUExecutionProvider"])
    target_path = file_path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_suffix(".tmp")
    try:
        with Image.open(file_path(original)) as source:
            normalized = ImageOps.exif_transpose(source).convert("RGBA")
            # Retain enough image detail without allocating matting buffers at 20 MP.
            normalized.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            mask = remove(normalized.convert("RGB"), session=session, only_mask=True)
            cutout = normalized.copy()
            # Preserve existing transparency instead of restoring hidden RGB pixels.
            cutout.putalpha(ImageChops.multiply(mask, normalized.getchannel("A")))
            bounds = cutout.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
            if bounds is None:
                raise ValueError("Model produced an empty foreground")
            cutout = cutout.crop(bounds)
            cutout.thumbnail((940, 940), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
            canvas.paste(cutout, ((1024 - cutout.width) // 2, (1024 - cutout.height) // 2))
            canvas.save(temporary, "PNG", exif=b"")
        temporary.replace(target_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "duration_ms": round((perf_counter() - started) * 1000),
        "model_version": f"rembg-{version('rembg')}/{model}",
    }


if __name__ == "__main__":
    print(json.dumps(create_cutout(*sys.argv[1:])))
