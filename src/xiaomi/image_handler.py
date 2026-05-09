from pathlib import Path
from src.xiaomi.client import XiaomiClient
from src.xiaomi.parser import ImageRef
from src.utils.console import console
from PIL import Image
import io


async def download_images(
    client: XiaomiClient,
    images: list[ImageRef],
    output_dir: Path,
) -> dict[str, Path]:
    """Download all images for a note. Returns file_id → local Path mapping."""
    if not images:
        return {}

    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    mapping: dict[str, Path] = {}
    for img in images:
        try:
            data = await client.download_file(img.file_id)
            ext = _detect_extension(data, img.ext)
            out_path = image_dir / f"{img.file_id}.{ext}"
            out_path.write_bytes(data)
            mapping[img.file_id] = out_path
        except Exception as e:
            console.print(f"  [yellow]Failed to download image {img.file_id}: {e}")

    return mapping


def _detect_extension(data: bytes, fallback: str) -> str:
    """Detect image format from bytes, fallback to provided extension."""
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format.lower() if img.format else fallback
        return {"jpeg": "jpg", "tiff": "tif"}.get(fmt, fmt)
    except Exception:
        return fallback
