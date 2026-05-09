from src.vivo.browser import VivoBrowser


class VivoAuth:
    """Handle Vivo authentication flow."""

    def __init__(self, browser: VivoBrowser):
        self.browser = browser

    async def login_if_needed(self, page):
        await self.browser.ensure_authenticated(page)
