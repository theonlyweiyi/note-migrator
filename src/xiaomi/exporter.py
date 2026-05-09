import json
from pathlib import Path
from src.config.schema import XiaomiConfig
from src.xiaomi.client import XiaomiClient
from src.xiaomi.parser import parse_note_html
from src.xiaomi.converter import NoteConverter
from src.xiaomi.image_handler import download_images
from src.utils.console import console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


class XiaomiExporter:
    """Orchestrate the export of all Xiaomi notes to Markdown files."""

    def __init__(self, config: XiaomiConfig, output_dir: Path):
        self.config = config
        self.output_dir = output_dir.resolve()
        self.client = XiaomiClient(config)
        self.converter = NoteConverter()

    async def export_all(self):
        notes_dir = self.output_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )

        with progress:
            # Step 1: Fetch all note metadata
            task_fetch = progress.add_task("Fetching note list...", total=None)
            all_notes = await self.client.list_all_notes()
            progress.update(task_fetch, completed=True)
            console.print(f"[info]Found {len(all_notes)} notes")

            if not all_notes:
                console.print("[yellow]No notes to export.")
                return

            # Step 2: Export each note
            task_export = progress.add_task(
                "Exporting notes...", total=len(all_notes)
            )
            manifest = []

            for note_meta in all_notes:
                try:
                    result = await self._export_single(note_meta.id, notes_dir)
                    manifest.append(result)
                except Exception as e:
                    console.print(f"  [red]Failed to export {note_meta.id}: {e}")
                    manifest.append({
                        "id": note_meta.id,
                        "title": note_meta.title,
                        "status": "failed",
                        "error": str(e),
                    })
                progress.advance(task_export)

        # Step 3: Write manifest
        manifest_path = self.output_dir / "export_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(f"[green]Export complete: {len(manifest)} notes")

    async def _export_single(self, note_id: str, notes_dir: Path) -> dict:
        note = await self.client.get_note_detail(note_id)
        parsed = parse_note_html(note.html_body)

        # Download images
        image_map = await download_images(self.client, parsed.images, self.output_dir)

        # Convert to Markdown
        markdown = self.converter.convert(
            parsed,
            title=note.title,
            create_time=note.create_time,
            update_time=note.update_time,
        )

        # Write file
        note_path = notes_dir / f"{note_id}.md"
        note_path.write_text(markdown, encoding="utf-8")

        return {
            "id": note_id,
            "title": note.title,
            "file": str(note_path.relative_to(self.output_dir)),
            "status": "exported",
            "image_count": len(parsed.images),
            "images": [str(p) for p in image_map.values()],
        }

    async def close(self):
        await self.client.close()


def verify_export(export_dir: Path):
    """Verify integrity of exported files."""
    import re

    export_dir = Path(export_dir)
    manifest_path = export_dir / "export_manifest.json"

    if not manifest_path.exists():
        console.print("[red]No export_manifest.json found.")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    notes_dir = export_dir / "notes"

    console.print(f"[info]Verifying {len(manifest)} exported notes...")

    issues = []
    for entry in manifest:
        note_file = notes_dir / f"{entry['id']}.md"
        if not note_file.exists():
            issues.append(f"Missing file: {entry['file']}")
            continue

        content = note_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            issues.append(f"Missing frontmatter: {entry['file']}")
        if not content.strip():
            issues.append(f"Empty file: {entry['file']}")

        # Check image references
        for img_path_str in entry.get("images", []):
            img_path = export_dir / img_path_str
            if not img_path.exists():
                issues.append(f"Missing image: {img_path_str}")

    if issues:
        for issue in issues:
            console.print(f"  [red]{issue}")
        console.print(f"[red]Found {len(issues)} issues")
    else:
        console.print("[green]All files verified OK")
