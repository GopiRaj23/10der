"""Input sanitisation for user-supplied strings (keywords, notes, profile
fields). Strips HTML and control characters to prevent stored XSS; keyword
text is additionally restricted to a safe character set."""
import re

_TAG_RE = re.compile(r"<[^>]*>")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# letters, digits, spaces and a few connectors used in tender terminology
_KEYWORD_ALLOWED = re.compile(r"^[\w\s\-&/().,'\"+]*$", re.UNICODE)


def strip_html(value: str) -> str:
    value = _TAG_RE.sub("", value or "")
    value = _CTRL_RE.sub("", value)
    return value.strip()


def clean_text(value: str | None, max_len: int = 2000) -> str | None:
    if value is None:
        return None
    return strip_html(value)[:max_len]


def validate_keyword(value: str) -> str:
    """Return a cleaned keyword or raise ValueError."""
    if _TAG_RE.search(value or ""):
        raise ValueError("Keyword must not contain HTML")
    cleaned = strip_html(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not (2 <= len(cleaned) <= 120):
        raise ValueError("Keyword must be between 2 and 120 characters")
    if not _KEYWORD_ALLOWED.match(cleaned):
        raise ValueError("Keyword contains invalid characters")
    return cleaned
