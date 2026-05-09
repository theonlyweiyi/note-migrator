import typer
from pathlib import Path
from src.config.loader import load_config, create_example_config
from src.config.schema import AppConfig
from src.utils.console import console

app = typer.Typer(
    name="note-migrator",
    help="Xiaomi Mi Notes → Vivo Atomic Notes Migration Tool",
    no_args_is_help=True,
)

# ── Config commands ──────────────────────────────────────────
config_app = typer.Typer(name="config", help="Manage configuration")
app.add_typer(config_app)


@config_app.command("init")
def config_init(config: Path = typer.Option("config.yaml", "-c", "--config")):
    """Create configuration interactively"""
    if config.exists():
        console.print(f"[yellow]Config file {config} already exists.")
        if not typer.confirm("Overwrite?"):
            return

    created = create_example_config(config)
    if created:
        console.print(f"[green]Created {config}")
        console.print("[info]Edit the file and fill in your Xiaomi cookies.")
    else:
        console.print("[red]config.example.yaml not found!")


@config_app.command("show")
def config_show(config: Path = typer.Option("config.yaml", "-c", "--config")):
    """Display current configuration"""
    try:
        cfg = load_config(config)
        console.print(cfg.model_dump_json(indent=2))
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}")


@config_app.command("validate")
def config_validate(config: Path = typer.Option("config.yaml", "-c", "--config")):
    """Validate that credentials work"""
    try:
        cfg = load_config(config)
    except Exception as e:
        console.print(f"[red]Config validation failed: {e}")
        raise typer.Exit(1)

    # Check Xiaomi cookies are filled
    x = cfg.xiaomi.auth
    if not x.service_token or not x.user_id:
        console.print("[red]Xiaomi credentials incomplete: service_token and user_id required")
        raise typer.Exit(1)
    console.print("[green]Config format is valid")

    # Validate by making a test API call
    from src.xiaomi.auth import validate_auth
    import asyncio

    async def _validate():
        ok = await validate_auth(cfg.xiaomi)
        if ok:
            console.print("[green]Xiaomi authentication: OK")
        else:
            console.print("[red]Xiaomi authentication: FAILED")
            console.print("[info]Cookies may be expired. Re-extract from browser.")
        return ok

    ok = asyncio.run(_validate())
    if not ok:
        raise typer.Exit(1)


# ── Export commands ──────────────────────────────────────────
export_app = typer.Typer(name="export", help="Phase 1: Export notes from Xiaomi Mi Notes")
app.add_typer(export_app)


@export_app.command("list")
def export_list(config: Path = typer.Option("config.yaml", "-c", "--config")):
    """List all notes on Xiaomi (without downloading)"""
    import asyncio
    from src.xiaomi.client import XiaomiClient
    from rich.table import Table

    cfg = load_config(config)

    async def _list():
        client = XiaomiClient(cfg.xiaomi)
        notes = await client.list_all_notes()
        if not notes:
            console.print("[yellow]No notes found.")
            return

        table = Table(title=f"Total: {len(notes)} notes")
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Updated")

        for n in notes:
            table.add_row(n.id, n.title or "(no title)", n.update_time or "")
        console.print(table)

    asyncio.run(_list())


@export_app.command("all")
def export_all(
    config: Path = typer.Option("config.yaml", "-c", "--config"),
    output: Path = typer.Option("output", "-o", "--output"),
):
    """Export all notes to Markdown files"""
    import asyncio
    from src.xiaomi.exporter import XiaomiExporter

    cfg = load_config(config)
    exporter = XiaomiExporter(cfg.xiaomi, output / "export")
    asyncio.run(exporter.export_all())


# ── Import commands ──────────────────────────────────────────
import_app = typer.Typer(name="import", help="Phase 2: Import notes into Vivo Atomic Notes")
app.add_typer(import_app)


@import_app.command("all")
def import_all(
    config: Path = typer.Option("config.yaml", "-c", "--config"),
    export_dir: Path = typer.Option("output/export", "-e", "--export-dir"),
):
    """Import all exported notes to Vivo"""
    import asyncio
    from src.vivo.importer import VivoImporter

    cfg = load_config(config)
    importer = VivoImporter(export_dir, cfg.vivo)
    asyncio.run(importer.import_all())


@import_app.command("status")
def import_status(
    export_dir: Path = typer.Option("output/export", "-e", "--export-dir"),
):
    """Show import status summary"""
    import json
    result_file = export_dir / "import_results.json"
    if not result_file.exists():
        console.print("[yellow]No import results found.")
        return

    results = json.loads(result_file.read_text(encoding="utf-8"))
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "imported")
    failed = sum(1 for r in results if r["status"] != "imported")
    console.print(f"[green]Imported: {ok}/{total}")
    if failed:
        console.print(f"[red]Failed/Partial: {failed}")


# ── Verify commands ──────────────────────────────────────────
verify_app = typer.Typer(name="verify", help="Verify export/import results")
app.add_typer(verify_app)


@verify_app.command("export")
def verify_export(
    export_dir: Path = typer.Option("output/export", "-e", "--export-dir"),
):
    """Check integrity of exported files"""
    from src.xiaomi.exporter import verify_export

    verify_export(export_dir)




# ── GUI command ─────────────────────────────────────────────
@app.command("gui")
def launch_gui():
    """Launch the graphical user interface"""
    import subprocess, sys
    gui_path = Path(__file__).parent.parent / "gui.py"
    if gui_path.exists():
        subprocess.run([sys.executable, str(gui_path)])
    else:
        console.print("[red]gui.py not found")


if __name__ == "__main__":
    app()
