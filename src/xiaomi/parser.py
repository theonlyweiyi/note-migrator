import re
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag


@dataclass
class ImageRef:
    file_id: str
    alt: str = ""
    ext: str = "jpg"


@dataclass
class ParsedContent:
    clean_html: str
    images: list[ImageRef] = field(default_factory=list)
    plain_text: str = ""


def parse_note_html(raw_html: str) -> ParsedContent:
    """Parse Xiaomi note HTML into clean, structured content."""
    if not raw_html.strip():
        return ParsedContent(clean_html="", plain_text="")

    soup = BeautifulSoup(raw_html, "html.parser")

    # Extract and rewrite image references
    images: list[ImageRef] = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        file_id = _extract_file_id(src)
        if file_id:
            ext = _guess_extension(img.get("src", ""))
            images.append(ImageRef(file_id=file_id, alt=img.get("alt", ""), ext=ext))
            img["src"] = f"images/{file_id}.{ext}"
        img.attrs = {k: v for k, v in img.attrs.items() if k in ("src", "alt")}

    # Convert Xiaomi checklists to Markdown-ish syntax
    _convert_checklists(soup)

    # Remove Xiaomi-specific wrapper attributes
    _clean_attributes(soup)

    clean_html = str(soup)
    plain_text = soup.get_text(separator="\n").strip()

    return ParsedContent(clean_html=clean_html, images=images, plain_text=plain_text)


def _extract_file_id(src: str) -> str | None:
    """Extract file ID from minote://image/{fileId} or similar URLs."""
    if not src:
        return None
    # minote://image/abc123
    m = re.search(r"minote://image/([^/\s?&]+)", src)
    if m:
        return m.group(1)
    # /api/file/get/abc123
    m = re.search(r"/file/get/([^/\s?&]+)", src)
    if m:
        return m.group(1)
    return None


def _guess_extension(src: str) -> str:
    """Guess file extension from URL."""
    m = re.search(r"\.(jpg|jpeg|png|gif|webp|bmp)(\?|$)", src.lower())
    return m.group(1) if m else "jpg"


def _convert_checklists(soup: BeautifulSoup):
    """Convert Xiaomi checklist items to Markdown task list syntax."""
    for li in soup.find_all("li"):
        classes = li.get("class", []) or []
        if isinstance(classes, str):
            classes = classes.split()
        if any("check" in c.lower() for c in classes):
            checkbox = li.find("input", attrs={"type": "checkbox"})
            if checkbox:
                checked = checkbox.get("checked") is not None
                marker = "[x]" if checked else "[ ]"
                checkbox.decompose()
                li.insert(0, soup.new_string(f"{marker} "))
                li["class"] = [c for c in classes if "check" not in c.lower()]


def _clean_attributes(soup: BeautifulSoup):
    """Remove Xiaomi-specific attributes while keeping formatting."""
    keep_tags = {
        "p", "br", "div", "span",
        "b", "strong", "i", "em", "u", "s", "strike", "code", "pre",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li",
        "table", "thead", "tbody", "tr", "th", "td",
        "blockquote", "a", "img",
    }
    for tag in soup.find_all(True):
        if tag.name not in keep_tags:
            tag.unwrap()
            continue
        # Strip all attributes except those critical for formatting
        attrs = {}
        for k, v in tag.attrs.items():
            if k == "href" and tag.name == "a":
                attrs[k] = v
            elif k in ("src", "alt") and tag.name == "img":
                attrs[k] = v
            elif k == "class":
                cls = v if isinstance(v, list) else v.split()
                formatting = [c for c in cls if any(
                    f in c for f in ("ql-", "note-")
                )]
                if formatting:
                    attrs[k] = formatting
        tag.attrs = attrs
