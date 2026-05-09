#!/usr/bin/env python3
"""Note Migrator GUI — 小米笔记 → Vivo 原子笔记 迁移工具"""
import asyncio, json
from pathlib import Path
import flet as ft

from src.config.loader import load_config, create_example_config
from src.xiaomi.auth import capture_cookies_via_playwright
from src.xiaomi.client import XiaomiClient
from src.xiaomi.exporter import XiaomiExporter
from src.vivo.browser import VivoBrowser
from src.vivo.importer import VivoImporter

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"

def _get_config():
    return load_config(CONFIG_PATH) if CONFIG_PATH.exists() else None


def _run_async(coro):
    """Run an async coroutine in a new event loop (for thread use)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class NoteMigratorApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.config = _get_config()

        # State
        self.xiaomi_connected = False
        self.xiaomi_note_count = 0
        self.vivo_logged_in = False

        # UI refs
        self.xiaomi_status = None
        self.xiaomi_notes_label = None
        self.xiaomi_export_btn = None
        self.xiaomi_progress = None
        self.xiaomi_log = None

        self.vivo_status = None
        self.vivo_import_btn = None
        self.vivo_progress = None
        self.vivo_log = None

        # Tab content containers
        self.xiaomi_page = None
        self.vivo_page = None
        self.tab_switcher = None

        self._setup_page()
        self._build_ui()

    # ── Page setup ──────────────────────────────────────────────
    def _setup_page(self):
        self.page.title = "Note Migrator — 笔记迁移工具"
        self.page.window.width = 760
        self.page.window.height = 820
        self.page.window.min_width = 600
        self.page.window.min_height = 600
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(primary=ft.Colors.BLUE_700),
        )

    # ── Log helper ──────────────────────────────────────────────
    def _log(self, area: ft.ListView, msg: str, color=None):
        if area is None:
            return
        area.controls.append(ft.Text(msg, size=13, color=color or ft.Colors.BLACK87))
        area.scroll_to(offset=-1, duration=300)
        self.page.update()

    # ── Card helper ─────────────────────────────────────────────
    @staticmethod
    def _card(content, padding=16):
        return ft.Container(
            content=content, padding=padding, border_radius=12,
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK12),
        )

    @staticmethod
    def _section_title(text):
        return ft.Text(text, size=12, weight=ft.FontWeight.BOLD,
                       color=ft.Colors.GREY_500)

    # ── Xiaomi tab ──────────────────────────────────────────────
    def _build_xiaomi(self):
        self.xiaomi_status = ft.Container(
            content=ft.Row([
                ft.Icon('cloud_off', color=ft.Colors.GREY_400, size=20),
                ft.Text("未连接", size=14, color=ft.Colors.GREY_700),
            ]),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=8, bgcolor=ft.Colors.GREY_100,
        )
        self.xiaomi_notes_label = ft.Text("共 0 篇笔记", size=14, color=ft.Colors.GREY_700)

        connect_btn = ft.Button("连接小米账号", icon='login',
                                on_click=self._on_xiaomi_connect)
        self.xiaomi_export_btn = ft.Button(
            "导出全部笔记", icon='download', disabled=True,
            on_click=self._on_xiaomi_export,
        )
        self.xiaomi_progress = ft.ProgressBar(value=0, visible=False)
        self.xiaomi_log = ft.ListView(spacing=2, height=260, auto_scroll=True)

        return ft.Container(
            content=ft.Column([
                self._card(ft.Column([
                    self._section_title("账号状态"),
                    self.xiaomi_status,
                    ft.Row([connect_btn], alignment=ft.MainAxisAlignment.END),
                ])),
                ft.Container(height=8),
                self._card(ft.Column([
                    ft.Row([
                        self._section_title("笔记导出"),
                        self.xiaomi_notes_label,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=4),
                    self.xiaomi_progress,
                    ft.Container(height=8),
                    self.xiaomi_export_btn,
                ])),
                ft.Container(height=8),
                self._card(ft.Column([
                    self._section_title("运行日志"),
                    ft.Container(
                        content=self.xiaomi_log, height=220,
                        border=ft.Border.all(1, ft.Colors.GREY_300),
                        border_radius=8, padding=8, bgcolor=ft.Colors.GREY_50,
                    ),
                ])),
            ]),
            padding=16, expand=True,
        )

    async def _on_xiaomi_connect(self, e):
        self.xiaomi_connected = False
        self.xiaomi_status.content = ft.Row([
            ft.ProgressRing(width=16, height=16),
            ft.Text("连接中...", size=14, color=ft.Colors.BLUE_700),
        ])
        self.page.update()

        def run():
            def cb(msg):
                self._log(self.xiaomi_log, msg, ft.Colors.BLUE_700)
            cb("正在打开浏览器窗口...")
            if not CONFIG_PATH.exists():
                create_example_config(CONFIG_PATH)
            return _run_async(capture_cookies_via_playwright(CONFIG_PATH, on_status=cb))

        ok = await self.page.run_thread(run)
        if ok:
            try:
                self.config = load_config(CONFIG_PATH)
                notes = await self.page.run_thread(lambda:
                    _run_async(_fetch_notes(self.config.xiaomi)))
                self.xiaomi_note_count = len(notes)
                self.xiaomi_connected = True
                self.xiaomi_status.content = ft.Row([
                    ft.Icon('cloud_done', color=ft.Colors.GREEN_600, size=20),
                    ft.Text(f"已连接", size=14, color=ft.Colors.GREEN_700),
                ])
                self.xiaomi_notes_label.value = f"共 {self.xiaomi_note_count} 篇笔记"
                self.xiaomi_export_btn.disabled = False
                self._log(self.xiaomi_log, f"连接成功！共 {self.xiaomi_note_count} 篇笔记",
                          ft.Colors.GREEN_700)
            except Exception as ex:
                self._log(self.xiaomi_log, f"连接测试失败: {ex}", ft.Colors.RED_700)
                self.xiaomi_status.content = ft.Row([
                    ft.Icon('error_outline', color=ft.Colors.RED_600, size=20),
                    ft.Text("连接失败", size=14, color=ft.Colors.RED_700),
                ])
        else:
            self._log(self.xiaomi_log, "小米账号连接失败", ft.Colors.RED_700)
        self.page.update()

    async def _on_xiaomi_export(self, e):
        if not self.xiaomi_connected:
            return
        self.xiaomi_export_btn.disabled = True
        self.xiaomi_progress.visible = True
        self.xiaomi_progress.value = None  # indeterminate
        self.page.update()

        output_dir = BASE_DIR / "output" / "export"
        self._log(self.xiaomi_log, "开始导出笔记...", ft.Colors.BLUE_700)
        await self.page.run_thread(lambda:
            _run_async(_do_export(self.config.xiaomi, output_dir)))
        self._log(self.xiaomi_log, f"导出完成！文件保存在 {output_dir}", ft.Colors.GREEN_700)

        self.xiaomi_progress.value = 1
        self.xiaomi_export_btn.disabled = False
        self.page.update()

    # ── Vivo tab ────────────────────────────────────────────────
    def _build_vivo(self):
        self.vivo_status = ft.Container(
            content=ft.Row([
                ft.Icon('cloud_off', color=ft.Colors.GREY_400, size=20),
                ft.Text("未登录", size=14, color=ft.Colors.GREY_700),
            ]),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=8, bgcolor=ft.Colors.GREY_100,
        )
        login_btn = ft.Button("登录Vivo账号", icon='login',
                              on_click=self._on_vivo_login)
        self.vivo_import_btn = ft.Button(
            "导入全部笔记", icon='upload_file', disabled=True,
            on_click=self._on_vivo_import,
        )
        self.vivo_progress = ft.ProgressBar(value=0, visible=False)
        self.vivo_log = ft.ListView(spacing=2, height=260, auto_scroll=True)

        return ft.Container(
            content=ft.Column([
                self._card(ft.Column([
                    self._section_title("登录状态"),
                    self.vivo_status,
                    ft.Row([login_btn], alignment=ft.MainAxisAlignment.END),
                ])),
                ft.Container(height=8),
                self._card(ft.Column([
                    self._section_title("导入笔记"),
                    self.vivo_progress,
                    ft.Container(height=8),
                    self.vivo_import_btn,
                ])),
                ft.Container(height=8),
                self._card(ft.Column([
                    self._section_title("运行日志"),
                    ft.Container(
                        content=self.vivo_log, height=220,
                        border=ft.Border.all(1, ft.Colors.GREY_300),
                        border_radius=8, padding=8, bgcolor=ft.Colors.GREY_50,
                    ),
                ])),
            ]),
            padding=16, expand=True,
        )

    async def _on_vivo_login(self, e):
        self.vivo_status.content = ft.Row([
            ft.ProgressRing(width=16, height=16),
            ft.Text("登录中...", size=14, color=ft.Colors.BLUE_700),
        ])
        self.page.update()

        self._log(self.vivo_log, "打开浏览器窗口，请在浏览器中登录Vivo...", ft.Colors.BLUE_700)
        ok = await self.page.run_thread(lambda:
            _run_async(_do_vivo_login(self.config.vivo)))

        if ok:
            self.vivo_logged_in = True
            self.vivo_status.content = ft.Row([
                ft.Icon('cloud_done', color=ft.Colors.GREEN_600, size=20),
                ft.Text("已登录", size=14, color=ft.Colors.GREEN_700),
            ])
            self.vivo_import_btn.disabled = False
            self._log(self.vivo_log, "Vivo 登录成功！", ft.Colors.GREEN_700)
        else:
            self._log(self.vivo_log, "Vivo 登录失败", ft.Colors.RED_700)
        self.page.update()

    async def _on_vivo_import(self, e):
        if not self.vivo_logged_in:
            return
        self.vivo_import_btn.disabled = True
        self.vivo_progress.visible = True
        self.vivo_progress.value = None
        self.page.update()

        export_dir = BASE_DIR / "output" / "export"
        self._log(self.vivo_log, "开始导入笔记到Vivo...", ft.Colors.BLUE_700)
        await self.page.run_thread(lambda:
            _run_async(_do_import(self.config, export_dir)))

        result_file = export_dir / "import_results.json"
        if result_file.exists():
            results = json.loads(result_file.read_text(encoding="utf-8"))
            ok = sum(1 for r in results if r["status"] == "imported")
            self._log(self.vivo_log, f"导入完成: {ok}/{len(results)} 篇", ft.Colors.GREEN_700)
        else:
            self._log(self.vivo_log, "导入完成，但未找到结果文件", ft.Colors.ORANGE_700)

        self.vivo_progress.value = 1
        self.vivo_import_btn.disabled = False
        self.page.update()

    # ── UI assembly ─────────────────────────────────────────────
    def _build_ui(self):
        header = ft.Container(
            content=ft.Row([
                ft.Icon("sync_alt", size=28, color=ft.Colors.BLUE_700),
                ft.Text("Note Migrator", size=22, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE_700),
                ft.Text("v0.2", size=12, color=ft.Colors.GREY_500),
            ], spacing=8),
            padding=ft.Padding.only(left=20, top=16, right=20, bottom=8),
        )
        help_banner = ft.Container(
            content=ft.Row([
                ft.Icon('info_outline', size=16, color=ft.Colors.BLUE_600),
                ft.Text("先连接小米账号导出笔记，再登录Vivo导入笔记",
                        size=13, color=ft.Colors.BLUE_800),
            ], spacing=8),
            padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            bgcolor=ft.Colors.BLUE_50,
        )

        # Build tab pages
        self.xiaomi_page = self._build_xiaomi()
        self.vivo_page = self._build_vivo()

        # Shared content area for Tabs
        self.tab_switcher = ft.Container(
            content=self.xiaomi_page, expand=True,
        )

        tabs = ft.Tabs(
            content=self.tab_switcher,
            length=2,
            selected_index=0,
            on_change=self._on_tab_change,
        )
        tabs.tabs = [
            ft.Tab(label="小米笔记", icon='cloud_download'),
            ft.Tab(label="Vivo原子笔记", icon='cloud_upload'),
        ]

        self.page.add(ft.Column([
            header, help_banner,
            ft.Container(content=tabs, expand=True),
        ], spacing=0, expand=True))

        # Check initial state
        if self.config and self.config.xiaomi.auth.service_token:
            self._log(self.xiaomi_log, "检测到已有小米cookies配置，可点「连接小米账号」更新",
                      ft.Colors.GREY_700)

    def _on_tab_change(self, e):
        idx = e.control.selected_index
        self.tab_switcher.content = self.xiaomi_page if idx == 0 else self.vivo_page
        self.page.update()


# ── Async helpers (run in threads) ─────────────────────────────
async def _fetch_notes(xiaomi_cfg):
    client = XiaomiClient(xiaomi_cfg)
    try:
        return await client.list_all_notes()
    finally:
        await client.close()

async def _do_export(xiaomi_cfg, output_dir):
    exporter = XiaomiExporter(xiaomi_cfg, output_dir)
    try:
        await exporter.export_all()
    finally:
        await exporter.close()

async def _do_vivo_login(vivo_cfg):
    browser = VivoBrowser(vivo_cfg)
    try:
        ctx = await browser.start()
        page = await ctx.new_page()
        await browser.ensure_authenticated(page)
        await browser.save_state()
        return True
    except Exception:
        return False
    finally:
        await browser.close()

async def _do_import(cfg, export_dir):
    importer = VivoImporter(export_dir, cfg.vivo)
    await importer.import_all()


# ── Entry point ────────────────────────────────────────────────
def main(page: ft.Page):
    NoteMigratorApp(page)

if __name__ == "__main__":
    ft.run(main)
