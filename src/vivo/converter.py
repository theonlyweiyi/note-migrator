import re
from markdown_it import MarkdownIt


class VivoHtmlConverter:
    """Convert Markdown to HTML suitable for Vivo editor injection."""

    def __init__(self):
        self.md = (
            MarkdownIt("commonmark", {"breaks": True, "html": True})
            .enable("table")
            .enable("strikethrough")
            .enable("tasklists")
        )

    def convert(self, markdown_content: str) -> str:
        """Convert Markdown to clean HTML for Vivo editor."""
        content = self._strip_frontmatter(markdown_content)
        if not content.strip():
            return ""

        html = self.md.render(content)
        html = self._wrap_content(html)
        return html

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """Remove YAML frontmatter (--- ... ---)."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content

    @staticmethod
    def _wrap_content(html: str) -> str:
        """Wrap content if multiple block elements to keep as single note."""
        block_count = len(re.findall(
            r'<(p|h[1-6]|ul|ol|table|div|blockquote|pre)\b', html
        ))
        if block_count > 1:
            return f"<div>{html}</div>"
        return html
