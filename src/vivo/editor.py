from playwright.async_api import Page, Locator
from src.utils.console import console
from bs4 import BeautifulSoup
import re


class VivoEditor:
    """Interact with the Vivo Atomic Notes web editor via Playwright."""

    # Possible editor selectors (tried in order)
    EDITOR_SELECTORS = [
        "div[contenteditable='true']",
        "div[contenteditable='plaintext-only']",
        ".ql-editor",
        ".ProseMirror",
        "[class*='editor']",
        "[class*='note-content']",
        "[class*='note-body']",
        "[class*='tiptap']",
    ]

    NEW_NOTE_SELECTORS = [
        "button:has-text('新建')",
        "button:has-text('新笔记')",
        "[class*='create'] button",
        "[class*='new-note']",
        "[class*='add-note']",
    ]

    IMAGE_BTN_SELECTORS = [
        "button:has-text('图片')",
        "button:has-text('Image')",
        "[class*='image'] button",
        "[title*='图片']",
        "[title*='Image']",
    ]

    def __init__(self, page: Page):
        self.page = page

    async def create_new_note(self) -> bool:
        """Click the 'New Note' button to create a blank note."""
        for selector in self.NEW_NOTE_SELECTORS:
            try:
                btn = self.page.locator(selector).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    await self.page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue

        # Fallback: try navigating
        try:
            await self.page.goto(
                "https://pc.vivo.com/#/notes/new", wait_until="networkidle"
            )
            await self.page.wait_for_timeout(2000)
            # If not redirected, we're probably on the new note page
            return True
        except Exception:
            pass

        console.print("[red]Could not find 'New Note' button")
        return False

    async def set_note_content(self, html_content: str) -> bool:
        """Set note content using tiered strategy."""
        # Tier 1: Direct innerHTML injection
        if await self._try_inner_html(html_content):
            return True

        # Tier 2: Clipboard paste
        if await self._try_clipboard_paste(html_content):
            return True

        # Tier 3: Plain text fallback
        console.print("[yellow]Falling back to plain text insertion")
        await self._type_plain_text(
            BeautifulSoup(html_content, "html.parser").get_text()
        )
        return True

    async def _find_editor(self) -> Locator | None:
        """Find the editor element on the page or in iframes."""
        # Direct page selectors
        for selector in self.EDITOR_SELECTORS:
            try:
                locator = self.page.locator(selector).first
                if await locator.is_visible(timeout=2000):
                    return locator
            except Exception:
                continue

        # Check iframes
        for frame in self.page.frames:
            for selector in self.EDITOR_SELECTORS:
                try:
                    locator = frame.locator(selector).first
                    if await locator.is_visible(timeout=1000):
                        return locator
                except Exception:
                    continue

        return None

    async def _try_inner_html(self, html: str) -> bool:
        """Tier 1: Direct innerHTML injection."""
        editor = await self._find_editor()
        if not editor:
            return False

        try:
            await editor.evaluate(
                f"""(el) => {{
                    el.innerHTML = arguments[0];
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));

                    // Trigger React/Vue reactivity
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLDivElement.prototype, 'innerHTML'
                    ).set;
                    nativeInputValueSetter.call(el, arguments[0]);
                    el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                }}""",
                html,
            )
            await self.page.wait_for_timeout(500)
            return True
        except Exception as e:
            console.print(f"  [yellow]innerHTML injection failed: {e}")
            return False

    async def _try_clipboard_paste(self, html: str) -> bool:
        """Tier 2: Use clipboard API to paste rich HTML."""
        try:
            await self.page.evaluate(
                """async (htmlContent) => {
                    const blob = new Blob([htmlContent], { type: 'text/html' });
                    const item = new ClipboardItem({ 'text/html': blob });
                    await navigator.clipboard.write([item]);
                }""",
                html,
            )

            editor = await self._find_editor()
            if editor:
                await editor.focus()
                await self.page.keyboard.press("Control+V")
                await self.page.wait_for_timeout(1000)
                return True
        except Exception as e:
            console.print(f"  [yellow]Clipboard paste failed: {e}")

        return False

    async def _type_plain_text(self, text: str):
        """Tier 3: Type plain text character by character."""
        editor = await self._find_editor()
        if editor:
            await editor.focus()
            await editor.fill(text)
            await self.page.wait_for_timeout(500)

    async def insert_image(self, image_path: str) -> bool:
        """Upload an image into the current note."""
        from pathlib import Path

        img_path = Path(image_path)
        if not img_path.exists():
            console.print(f"  [red]Image not found: {image_path}")
            return False

        # Strategy 1: Direct file input
        try:
            file_input = self.page.locator('input[type="file"]').first
            if await file_input.is_visible(timeout=2000):
                await file_input.set_input_files(str(img_path.absolute()))
                await self.page.wait_for_timeout(2000)
                return True
        except Exception:
            pass

        # Strategy 2: Hidden file input
        try:
            all_inputs = self.page.locator('input[type="file"]')
            count = await all_inputs.count()
            if count > 0:
                await all_inputs.first.set_input_files(str(img_path.absolute()))
                await self.page.wait_for_timeout(2000)
                return True
        except Exception:
            pass

        # Strategy 3: Click image button → file chooser
        for selector in self.IMAGE_BTN_SELECTORS:
            try:
                async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                    btn = self.page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(img_path.absolute()))
                        await self.page.wait_for_timeout(2000)
                        return True
            except Exception:
                continue

        console.print(f"  [yellow]Could not upload image: {image_path}")
        return False
