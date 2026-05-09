import json
from pathlib import Path
from src.config.schema import VivoConfig
from src.vivo.browser import VivoBrowser
from src.vivo.editor import VivoEditor
from src.vivo.converter import VivoHtmlConverter
from src.utils.console import console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn


class VivoImporter:
    """Orchestrate importing exported notes into Vivo Atomic Notes."""

    def __init__(self, export_dir: Path, config: VivoConfig):
        self.export_dir = export_dir.resolve()
        self.config = config
        self.browser = VivoBrowser(config)
        self.converter = VivoHtmlConverter()

    async def import_all(self):
        manifest_path = self.export_dir / "export_manifest.json"
        if not manifest_path.exists():
            console.print("[red]No export_manifest.json found. Run 'export all' first.")
            return

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checkpoint_path = Path(self.config.session_file).parent / "import_checkpoint.json"

        console.print(f"[info]Starting import of {len(manifest)} notes")

        # Start browser
        context = await self.browser.start()
        page = await context.new_page()

        # Authenticate
        await self.browser.ensure_authenticated(page)
        editor = VivoEditor(page)

        # Load checkpoint
        imported_ids = self._load_checkpoint(checkpoint_path)
        remaining = [n for n in manifest if n["id"] not in imported_ids and n.get("status") == "exported"]
        console.print(f"[info]Already imported: {len(imported_ids)}, remaining: {len(remaining)}")

        # Import notes
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )

        results = list(imported_ids)

        with progress:
            task = progress.add_task("Importing notes...", total=len(remaining))

            for entry in remaining:
                note_id = entry["id"]
                try:
                    success = await self._import_single(editor, entry)
                    if success:
                        results.append(note_id)
                        self._save_checkpoint(checkpoint_path, results)
                        progress.advance(task)
                    else:
                        console.print(f"  [red]Failed to import note {entry['title']}")
                        progress.advance(task)
                except Exception as e:
                    console.print(f"  [red]Error importing {entry['title']}: {e}")
                    progress.advance(task)

                # Delay between notes
                import asyncio
                await asyncio.sleep(self.config.typing_delay_ms / 1000)

        # Save summary
        result_path = self.export_dir / "import_results.json"
        result_data = [
            {"id": nid, "status": "imported"} for nid in results
        ]
        result_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        console.print(f"[green]Import complete: {len(results)}/{len(manifest)} notes")

        await self.browser.close()

    async def _import_single(self, editor: VivoEditor, entry: dict) -> bool:
        """Import a single note into Vivo."""
        note_path = self.export_dir / entry["file"]
        if not note_path.exists():
            console.print(f"  [red]Note file not found: {entry['file']}")
            return False

        markdown = note_path.read_text(encoding="utf-8")
        html = self.converter.convert(markdown)

        # Create new note
        ok = await editor.create_new_note()
        if not ok:
            return False

        # Wait for editor to be ready
        import asyncio
        await asyncio.sleep(1)

        # Set content
        ok = await editor.set_note_content(html)
        if not ok:
            return False

        # Upload images
        image_paths = entry.get("images", [])
        if image_paths:
            from src.vivo.image_handler import upload_images
            image_results = await upload_images(editor, image_paths)
            if not all(image_results):
                console.print(f"  [yellow]Some images failed for {entry['title']}")

        return True

    @staticmethod
    def _load_checkpoint(path: Path) -> set:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return set(data.get("imported_ids", []))
        return set()

    @staticmethod
    def _save_checkpoint(path: Path, imported_ids: list):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"imported_ids": imported_ids}, indent=2),
            encoding="utf-8",
        )
