import httpx
from src.config.schema import XiaomiConfig


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


def _make_cookies(config: XiaomiConfig) -> dict:
    cookies = {
        "serviceToken": config.auth.service_token,
        "userId": config.auth.user_id,
    }
    if config.auth.pass_token:
        cookies["passToken"] = config.auth.pass_token
    return cookies
