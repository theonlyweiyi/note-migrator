import httpx
import yaml
from pathlib import Path
from src.config.schema import XiaomiConfig, XiaomiAuth


REQUIRED_COOKIES = ["serviceToken", "userId"]


async def validate_auth(config: XiaomiConfig) -> bool:
    """Validate Xiaomi cookies by making a minimal API call."""
    client = httpx.AsyncClient(
        base_url=config.base_url,
        cookies=_make_cookies(config),
        timeout=config.request_timeout,
        follow_redirects=True,
    )
    try:
        resp = await client.get("/api/note/list", params={"pageSize": 1})
        return resp.status_code == 200
    except Exception:
        return False
    finally:
        await client.aclose()


async def capture_cookies_via_playwright(
    config_path: Path,
    on_status: callable = None,
) -> bool:
    """Open a Playwright browser, let user log in to i.mi.com, auto-capture cookies."""
    from playwright.async_api import async_playwright

    if on_status:
        on_status("正在打开浏览器窗口，请登录小米账号...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://i.mi.com/note")

        if on_status:
            on_status("请在浏览器中登录小米账号，登录后会自动捕获...")

        # Wait for user to reach the notes page (indicating login success)
        # i.mi.com/note loads the note list only when authenticated
        try:
            await page.wait_for_url("**/note**", timeout=0)
        except Exception:
            pass

        # Give the page a moment to fully load
        await page.wait_for_timeout(3000)

        # Capture cookies from the browser context
        cookies = await context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        missing = [k for k in REQUIRED_COOKIES if k not in cookie_dict]
        if missing:
            if on_status:
                on_status(f"未找到必要 cookies: {missing}，请确保已成功登录")
            await browser.close()
            return False

        # Save cookies to config file
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        else:
            cfg = {}

        if "xiaomi" not in cfg:
            cfg["xiaomi"] = {}
        if "auth" not in cfg["xiaomi"]:
            cfg["xiaomi"]["auth"] = {}

        cfg["xiaomi"]["auth"]["service_token"] = cookie_dict.get("serviceToken", "")
        cfg["xiaomi"]["auth"]["user_id"] = cookie_dict.get("userId", "")
        cfg["xiaomi"]["auth"]["pass_token"] = cookie_dict.get("passToken", "")

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

        await browser.close()

    if on_status:
        on_status(f"✅ 小米账号已连接！userId: {cookie_dict.get('userId', '')[:6]}...")

    return True


def _make_cookies(config: XiaomiConfig) -> dict:
    cookies = {
        "serviceToken": config.auth.service_token,
        "userId": config.auth.user_id,
    }
    if config.auth.pass_token:
        cookies["passToken"] = config.auth.pass_token
    return cookies
