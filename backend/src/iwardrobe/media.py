from io import BytesIO
from pathlib import Path
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings

Image.MAX_IMAGE_PIXELS = 20_000_000
FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


def file_path(key: str) -> Path:
    root = settings().data_dir.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid media key")
    return path


def inspect_image(data: bytes) -> tuple[str, str, int, int]:
    if not data or len(data) > settings().max_upload_bytes:
        raise HTTPException(413, "图片不能为空且必须小于 20 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as im:
                if im.format not in FORMATS or getattr(im, "n_frames", 1) != 1:
                    raise HTTPException(415, "当前支持单张 JPEG、PNG、WebP，请先转换 HEIC 或动态图")
                ext, content_type = FORMATS[im.format]
                width, height = im.size
                im.verify()
            with Image.open(BytesIO(data)) as im:
                im.load()
        return ext, content_type, width, height
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        ValueError,
    ):
        raise HTTPException(415, "图片无法读取，或超过 2000 万像素限制") from None


def write_original(key: str, data: bytes) -> Path:
    path = file_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def thumbnail(original: str, target: str) -> None:
    target_path = file_path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_suffix(".tmp")
    try:
        with Image.open(file_path(original)) as im:
            normalized = ImageOps.exif_transpose(im).convert("RGBA")
            normalized.thumbnail((800, 800), Image.Resampling.LANCZOS)
            normalized.save(temporary, "WEBP", quality=88, exif=b"")
        temporary.replace(target_path)
    finally:
        temporary.unlink(missing_ok=True)
