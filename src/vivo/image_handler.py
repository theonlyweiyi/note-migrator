from pathlib import Path
from src.vivo.editor import VivoEditor


async def upload_images(editor: VivoEditor, image_paths: list[str]) -> list[bool]:
    """Upload multiple images to the current note."""
    results = []
    for img_path in image_paths:
        ok = await editor.insert_image(img_path)
        results.append(ok)
    return results
