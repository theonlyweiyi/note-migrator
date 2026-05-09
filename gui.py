#!/usr/bin/env python3
"""
Note Migrator GUI — 小米笔记 → Vivo 原子笔记 迁移工具
Usage: python gui.py
"""
import asyncio
import json
import os
from pathlib import Path
import threading
import flet as ft

# We import sync wrappers since Flet runs its own event loop
from src.config.loader import load_config
from src.config.schema import XiaomiConfig, VivoConfig
from src.xiaomi.auth import capture_cookies_via_playwright
from src.xiaomi.client import XiaomiClient
from src.xiaomi.exporter import XiaomiExporter
from src.vivo.browser import VivoBrowser
from src.vivo.importer import VivoImporter

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"


def _get_config():
    if CONFIG_PATH.exists():
        return load_config(CONFIG_PATH)
    return None


def _status(msg: str):
    """Helper to format status messages for log."""
    return msg


# ── Main Application ──────────────────────────────────────────────
class NoteMigratorApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.config = _get_config()

        # Xiaomi state
        self.xiaomi_connected = False
        self.xiaomi_note_count = 0

        # Vivo state
        self.vivo_logged_in = False

        # UI refs (set during build)
        self.xiaomi_status = None
        self.xiaomi_notes_label = None
        self.xiaomi_export_btn = None
        self.xiaomi_progress = None
        self.xiaomi_log = None

        self.vivo_status = None
        self.vivo_import_btn = None
        self.vivo_progress = None
        self.vivo_log = None

        self.setup_page()
        self.build_ui()

    def setup_page(self):
        self.page.title = "Note Migrator — 笔记迁移工具"
        self.page.window.width = 760
        self.page.window.height = 820
        self.page.window.min_width = 600
        self.page.window.min_height = 600
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.padding = 0
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=ft.Colors.BLUE_700,
            ),
        )

    # ── Log helper ────────────────────────────────────────────────
    def log(self, area: ft.ListView, msg: str, color: str = None):
        """Append a log entry to a ListView."""
        if area is None:
            return
        t = ft.Text(msg, size=13, color=color or ft.Colors.BLACK87)
        area.controls.append(t)
        area.scroll_to(offset=-1, duration=300)
        self.page.update()

    # ── Xiaomi Tab ────────────────────────────────────────────────
    def build_xiaomi_tab(self):
        self.xiaomi_status = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.CLOUD_OFF, color=ft.Colors.GREY_400, size=20),
                ft.Text("未连接", size=14, color=ft.Colors.GREY_700),
            ]),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.GREY_100,
        )

        self.xiaomi_notes_label = ft.Text("共 0 篇笔记", size=14, color=ft.Colors.GREY_700)

        connect_btn = ft.ElevatedButton(
            "🔗  连接小米账号",
            icon=ft.icons.LOGIN,
            on_click=self.on_xiaomi_connect,
        )

        self.xiaomi_export_btn = ft.ElevatedButton(
            "📥  导出全部笔记",
            icon=ft.icons.DOWNLOAD,
            disabled=True,
            on_click=self.on_xiaomi_export,
        )

        self.xiaomi_progress = ft.ProgressBar(value=0, visible=False)

        self.xiaomi_log = ft.ListView(
            spacing=2,
            height=300,
            auto_scroll=True,
        )

        return ft.Container(
            content=ft.Column([
                # Status card
                ft.Container(
                    content=ft.Column([
                        ft.Text("账号状态", size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_500),
                        self.xiaomi_status,
                        ft.Row([connect_btn], alignment=ft.MainAxisAlignment.END),
                    ]),
                    padding=16,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
                ),

                ft.Container(height=8),

                # Export card
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text("笔记导出", size=12, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREY_500),
                            self.xiaomi_notes_label,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        self.xiaomi_progress,
                        ft.Container(height=8),
                        self.xiaomi_export_btn,
                    ]),
                    padding=16,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
                ),

                ft.Container(height=8),

                # Log card
                ft.Container(
                    content=ft.Column([
                        ft.Text("运行日志", size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_500),
                        ft.Container(
                            content=self.xiaomi_log,
                            height=260,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=8,
                            padding=8,
                            bgcolor=ft.Colors.GREY_50,
                        ),
                    ]),
                    padding=16,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
                ),
            ]),
            padding=16,
            expand=True,
        )

    async def on_xiaomi_connect(self, e):
        self.xiaomi_connected = False
        self.xiaomi_status.content = ft.Row([
            ft.ProgressRing(width=16, height=16),
            ft.Text("连接中...", size=14, color=ft.Colors.BLUE_700),
        ])
        self.page.update()

        # Run cookie capture in executor to not block Flet
        def capture():
            async def _run():
                success = False
                def status_cb(msg):
                    self.log(self.xiaomi_log, msg, ft.Colors.BLUE_700)

                status_cb("正在打开浏览器窗口...")

                # Create config if missing
                if not CONFIG_PATH.exists():
                    from src.config.loader import create_example_config
                    create_example_config(CONFIG_PATH)

                ok = await capture_cookies_via_playwright(CONFIG_PATH, on_status=status_cb)
                return ok

            # Need new event loop in thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_run())
            finally:
                loop.close()

        result = await self.page.run_thread(capture)

        if result:
            # Reload config and test connection
            try:
                self.config = load_config(CONFIG_PATH)
                client = XiaomiClient(self.config.xiaomi)

                def fetch_notes():
                    async def _fetch():
                        notes = await client.list_all_notes()
                        await client.close()
                        return notes
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(_fetch())
                    finally:
                        loop.close()

                notes = await self.page.run_thread(fetch_notes)
                self.xiaomi_note_count = len(notes)

                self.xiaomi_connected = True
                self.xiaomi_status.content = ft.Row([
                    ft.Icon(ft.icons.CLOUD_DONE, color=ft.Colors.GREEN_600, size=20),
                    ft.Text(f"已连接 ({self.config.xiaomi.auth.user_id[:6]}...)",
                            size=14, color=ft.Colors.GREEN_700),
                ])
                self.xiaomi_notes_label.value = f"共 {self.xiaomi_note_count} 篇笔记"
                self.xiaomi_export_btn.disabled = False
                self.log(self.xiaomi_log, f"✅ 连接成功！共 {self.xiaomi_note_count} 篇笔记",
                         ft.Colors.GREEN_700)
            except Exception as ex:
                self.log(self.xiaomi_log, f"❌ 连接测试失败: {ex}", ft.Colors.RED_700)
                self.xiaomi_status.content = ft.Row([
                    ft.Icon(ft.icons.ERROR_OUTLINE, color=ft.Colors.RED_600, size=20),
                    ft.Text("连接失败", size=14, color=ft.Colors.RED_700),
                ])
        else:
            self.log(self.xiaomi_log, "❌ 小米账号连接失败", ft.Colors.RED_700)

        self.page.update()

    async def on_xiaomi_export(self, e):
        if not self.xiaomi_connected:
            return

        self.xiaomi_export_btn.disabled = True
        self.xiaomi_progress.visible = True
        self.xiaomi_progress.value = 0
        self.page.update()

        output_dir = BASE_DIR / "output" / "export"

        # Run export in thread
        def do_export():
            async def _export():
                exporter = XiaomiExporter(self.config.xiaomi, output_dir)
                try:
                    await exporter.export_all()
                finally:
                    await exporter.close()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_export())
            finally:
                loop.close()

        self.log(self.xiaomi_log, "开始导出笔记...", ft.Colors.BLUE_700)
        await self.page.run_thread(do_export)
        self.log(self.xiaomi_log, f"✅ 导出完成！文件保存在 {output_dir}", ft.Colors.GREEN_700)

        self.xiaomi_progress.value = 1
        self.xiaomi_export_btn.disabled = False
        self.page.update()

    # ── Vivo Tab ──────────────────────────────────────────────────
    def build_vivo_tab(self):
        self.vivo_status = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.CLOUD_OFF, color=ft.Colors.GREY_400, size=20),
                ft.Text("未登录", size=14, color=ft.Colors.GREY_700),
            ]),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.GREY_100,
        )

        login_btn = ft.ElevatedButton(
            "🔗  登录 Vivo 账号",
            icon=ft.icons.LOGIN,
            on_click=self.on_vivo_login,
        )

        self.vivo_import_btn = ft.ElevatedButton(
            "📤  导入全部笔记",
            icon=ft.icons.UPLOAD_FILE,
            disabled=True,
            on_click=self.on_vivo_import,
        )

        self.vivo_progress = ft.ProgressBar(value=0, visible=False)

        self.vivo_log = ft.ListView(
            spacing=2,
            height=300,
            auto_scroll=True,
        )

        return ft.Container(
            content=ft.Column([
                # Status card
                ft.Container(
                    content=ft.Column([
                        ft.Text("登录状态", size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_500),
                        self.vivo_status,
                        ft.Row([login_btn], alignment=ft.MainAxisAlignment.END),
                    ]),
                    padding=16,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
                ),

                ft.Container(height=8),

                # Import card
                ft.Container(
                    content=ft.Column([
                        ft.Text("导入笔记", size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_500),
                        self.vivo_progress,
                        ft.Container(height=8),
                        self.vivo_import_btn,
                    ]),
                    padding=16,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
                ),

                ft.Container(height=8),

                # Log card
                ft.Container(
                    content=ft.Column([
                        ft.Text("运行日志", size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_500),
                        ft.Container(
                            content=self.vivo_log,
                            height=260,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=8,
                            padding=8,
                            bgcolor=ft.Colors.GREY_50,
                        ),
                    ]),
                    padding=16,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
                ),
            ]),
            padding=16,
            expand=True,
        )

    async def on_vivo_login(self, e):
        self.vivo_status.content = ft.Row([
            ft.ProgressRing(width=16, height=16),
            ft.Text("登录中...", size=14, color=ft.Colors.BLUE_700),
        ])
        self.page.update()

        def login():
            async def _login():
                if not self.config:
                    return False
                browser = VivoBrowser(self.config.vivo)
                try:
                    context = await browser.start()
                    page = await context.new_page()
                    await browser.ensure_authenticated(page)
                    await browser.save_state()
                    return True
                finally:
                    await browser.close()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_login())
            finally:
                loop.close()

        self.log(self.vivo_log, "打开浏览器窗口，请在浏览器中登录 Vivo...", ft.Colors.BLUE_700)
        result = await self.page.run_thread(login)

        if result:
            self.vivo_logged_in = True
            self.vivo_status.content = ft.Row([
                ft.Icon(ft.icons.CLOUD_DONE, color=ft.Colors.GREEN_600, size=20),
                ft.Text("已登录", size=14, color=ft.Colors.GREEN_700),
            ])
            self.vivo_import_btn.disabled = False
            self.log(self.vivo_log, "✅ Vivo 登录成功！", ft.Colors.GREEN_700)
        else:
            self.log(self.vivo_log, "❌ Vivo 登录失败", ft.Colors.RED_700)

        self.page.update()

    async def on_vivo_import(self, e):
        if not self.vivo_logged_in:
            return

        self.vivo_import_btn.disabled = True
        self.vivo_progress.visible = True
        self.vivo_progress.value = 0
        self.page.update()

        export_dir = BASE_DIR / "output" / "export"

        def do_import():
            async def _import():
                cfg = self.config
                importer = VivoImporter(export_dir, cfg.vivo)
                await importer.import_all()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_import())
            finally:
                loop.close()

        self.log(self.vivo_log, "开始导入笔记到 Vivo...", ft.Colors.BLUE_700)
        await self.page.run_thread(do_import)

        # Check result
        result_file = export_dir / "import_results.json"
        if result_file.exists():
            results = json.loads(result_file.read_text(encoding="utf-8"))
            ok = sum(1 for r in results if r["status"] == "imported")
            self.log(self.vivo_log, f"✅ 导入完成: {ok}/{len(results)} 篇", ft.Colors.GREEN_700)
        else:
            self.log(self.vivo_log, "⚠️ 导入完成，但未找到结果文件", ft.Colors.ORANGE_700)

        self.vivo_progress.value = 1
        self.vivo_import_btn.disabled = False
        self.page.update()

    # ── Build UI ──────────────────────────────────────────────────
    def build_ui(self):
        # Header
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.SYNC_ALT, size=28, color=ft.Colors.BLUE_700),
                ft.Text("Note Migrator", size=22, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE_700),
                ft.Text("v0.2", size=12, color=ft.Colors.GREY_500),
            ], spacing=8),
            padding=ft.padding.only(left=20, top=16, right=20, bottom=8),
        )

        # Help banner
        help_banner = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.INFO_OUTLINE, size=16, color=ft.Colors.BLUE_600),
                ft.Text("先连接小米账号导出笔记，再登录Vivo导入笔记",
                        size=13, color=ft.Colors.BLUE_800),
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=20, vertical=8),
            bgcolor=ft.Colors.BLUE_50,
        )

        # Tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="  小米笔记  ",
                    icon=ft.icons.CLOUD_DOWNLOAD,
                    content=self.build_xiaomi_tab(),
                ),
                ft.Tab(
                    text="  Vivo原子笔记  ",
                    icon=ft.icons.CLOUD_UPLOAD,
                    content=self.build_vivo_tab(),
                ),
            ],
        )

        # Build the page
        self.page.add(
            ft.Column([
                header,
                help_banner,
                ft.Container(content=tabs, expand=True),
            ], spacing=0, expand=True),
        )

        # Check initial config state
        self._check_initial_state()

    def _check_initial_state(self):
        """Check if config exists and has credentials on startup."""
        if self.config and self.config.xiaomi.auth.service_token:
            log = self.xiaomi_log
            self.log(log, "ℹ️ 检测到已有小米 cookies 配置", ft.Colors.GREY_700)
            self.log(log, "点击「连接小米账号」可重新登录更新 cookies", ft.Colors.GREY_700)


# ── Entry Point ──────────────────────────────────────────────────
def main():
    ft.app(target=NoteMigratorApp)


if __name__ == "__main__":
    main()
