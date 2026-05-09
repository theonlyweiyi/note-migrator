import html2text
from src.xiaomi.parser import ParsedContent


class NoteConverter:
    """Convert parsed Xiaomi HTML to Markdown with YAML frontmatter."""

    def __init__(self):
        self._converter = html2text.HTML2Text()
        self._converter.body_width = 0
        self._converter.ignore_links = False
        self._converter.ignore_images = False
        self._converter.protect_links = True
        self._converter.use_automatic_links = True
        self._converter.single_line_break = True
        self._converter.mark_code = True

    def convert(
        self,
        parsed: ParsedContent,
        title: str = "",
        create_time: str = "",
        update_time: str = "",
    ) -> str:
        """Convert parsed content to Markdown with frontmatter."""
        parts = ["---"]

        if title:
            parts.append(f"title: {title}")
        if create_time:
            parts.append(f"created: {create_time}")
        if update_time:
            parts.append(f"updated: {update_time}")
        if parsed.images:
            ids = ", ".join(img.file_id for img in parsed.images)
            parts.append(f"images: [{ids}]")

        parts.append("---\n")

        if parsed.clean_html:
            body = self._converter.handle(parsed.clean_html)
            parts.append(body.strip())
        elif parsed.plain_text:
            parts.append(parsed.plain_text)

        return "\n\n".join(parts)
