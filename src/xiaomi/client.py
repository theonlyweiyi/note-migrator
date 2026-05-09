import httpx
from dataclasses import dataclass, field
from typing import Optional
from src.config.schema import XiaomiConfig


@dataclass
class NoteMeta:
    id: str
    title: str
    summary: str = ""
    create_time: str = ""
    update_time: str = ""
    folder_id: str = ""
    archived: bool = False


@dataclass
class NoteContent:
    id: str
    title: str
    html_body: str
    create_time: str = ""
    update_time: str = ""
    tags: list[str] = field(default_factory=list)


class XiaomiClient:
    """HTTP client for the Xiaomi Mi Notes internal API."""

    def __init__(self, config: XiaomiConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            cookies=self._make_cookies(),
            timeout=config.request_timeout,
            follow_redirects=True,
        )
        self._endpoints = self._default_endpoints()
        self._discovered = False

    def _make_cookies(self) -> dict:
        c = {
            "serviceToken": self.config.auth.service_token,
            "userId": self.config.auth.user_id,
        }
        if self.config.auth.pass_token:
            c["passToken"] = self.config.auth.pass_token
        return c

    @staticmethod
    def _default_endpoints() -> dict:
        return {
            "list": "/api/note/list",
            "get": "/api/note/get",
            "file": "/api/file/get",
        }

    async def _ensure_discovered(self):
        """Try known endpoints to find which ones work."""
        if self._discovered:
            return
        # Try the default list endpoint first
        try:
            resp = await self._client.get(
                self._endpoints["list"], params={"pageSize": 1}
            )
            if resp.status_code == 200:
                self._discovered = True
                return
        except Exception:
            pass

        # Fallback: try alternative paths
        alternatives = {
            "list": ["/note/home", "/note/full/page"],
        }
        for path in alternatives.get("list", []):
            try:
                resp = await self._client.get(path)
                if resp.status_code == 200:
                    self._endpoints["list"] = path
                    self._discovered = True
                    return
            except Exception:
                continue

        self._discovered = True

    async def list_notes(self, page: int = 0, page_size: int = 50) -> dict:
        """Get paginated note list. Returns raw JSON response."""
        await self._ensure_discovered()
        resp = await self._client.get(
            self._endpoints["list"],
            params={"pageNum": page, "pageSize": page_size},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_all_notes(self) -> list[NoteMeta]:
        """Fetch all notes across all pages."""
        all_notes = []
        page = 0

        while True:
            data = await self.list_notes(page=page)
            items = data.get("data", data.get("notes", data.get("list", [])))
            if isinstance(items, dict):
                items = items.get("list", items)

            if not items:
                break

            for item in items:
                all_notes.append(NoteMeta(
                    id=str(item.get("id", "")),
                    title=item.get("title", item.get("name", "")),
                    summary=item.get("summary", item.get("snippet", "")),
                    create_time=item.get("createTime", item.get("create_time", "")),
                    update_time=item.get("updateTime", item.get("update_time", "")),
                    folder_id=str(item.get("folderId", item.get("folder_id", ""))),
                    archived=item.get("archived", item.get("isArchive", False)),
                ))

            # Check pagination
            total_pages = data.get("totalPages", 1)
            if page >= total_pages - 1:
                break
            page += 1

        return all_notes

    async def get_note_detail(self, note_id: str) -> NoteContent:
        """Get full note content with HTML body."""
        resp = await self._client.get(
            self._endpoints["get"], params={"id": note_id}
        )
        resp.raise_for_status()
        data = resp.json()
        note_data = data.get("data", data)

        return NoteContent(
            id=str(note_data.get("id", note_id)),
            title=note_data.get("title", ""),
            html_body=note_data.get("content", note_data.get("htmlBody", "")),
            create_time=note_data.get("createTime", note_data.get("create_time", "")),
            update_time=note_data.get("updateTime", note_data.get("update_time", "")),
            tags=note_data.get("tags", []),
        )

    async def download_file(self, file_id: str) -> bytes:
        """Download image/attachment by fileId."""
        resp = await self._client.get(f"{self._endpoints['file']}/{file_id}")
        resp.raise_for_status()
        return resp.content

    async def close(self):
        await self._client.aclose()
