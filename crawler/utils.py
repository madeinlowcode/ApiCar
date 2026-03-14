"""URL helpers and utilities for the crawler."""
import base64
import hashlib
import json


def decode_catalog_url(url: str) -> dict | None:
    """Extract and decode the base64 'l=' parameter from a catalog URL."""
    from urllib.parse import urlparse, parse_qs
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "l" in params:
            decoded = base64.b64decode(params["l"][0]).decode("utf-8")
            return json.loads(decoded) if decoded.startswith("{") else {"raw": decoded}
    except Exception:
        return None


def generate_content_hash(content: str) -> str:
    """Generate SHA256 hash of page content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def ensure_english_url(url: str) -> str:
    """Ensure the URL has lang=en parameter so the site renders in English."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["lang"] = ["en"]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text
