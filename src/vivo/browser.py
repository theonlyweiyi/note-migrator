import json
from pathlib import Path
from src.utils.console import console
from src.config.schema import VivoConfig
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class VivoBrowser:
    """Manage Playwright browser lifecycle for Vivo Atomic Notes."""

    def __init__(self, config: VivoConfig):
        self.config = config
        self.state_file = Path(config.session_file)
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def start(self, headless: bool | None = None) -> BrowserContext:
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless if headless is not None else self.config.headless,
        )

        if self.state_file.exists():
            self.context = await self.browser.new_context(
                storage_state=str(self.state_file),
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
        else:
            self.context = await self.browser.new_context(
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )

        return self.context

    async def save_state(self):
        if self.context and self.state_file:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            await self.context.storage_state(path=str(self.state_file))
            console.print(f"[green]Session saved to {self.state_file}")

    async def ensure_authenticated(self, page: Page):
        """Check if logged in; if not, prompt user to login."""
        await page.goto(f"{self.config.base_url}/#/notes", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Check if redirected to login page
        current_url = page.url
        if "login" in current_url.lower() or "auth" in current_url.lower():
            console.print("[yellow]Please log in to Vivo in the browser window.")
            console.print("[yellow]After logging in, press Enter to continue...")
            input()
            await self.save_state()
            # Navigate back to notes
            await page.goto(f"{self.config.base_url}/#/notes", wait_until="networkidle")
            await page.wait_for_timeout(2000)

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
