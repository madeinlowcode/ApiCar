"""Parsers for brand navigation pages on catcar.info.

Handles year tabs, region/market links, table links, groups-parts links,
and auto-detection of page types for Honda, Kia, Nissan, Mazda, Subaru,
Hyundai, and Chrysler brands.
"""
import base64
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


def _decode_l_param(url: str) -> str:
    """Decode the base64-encoded 'l' query parameter from a catcar URL.

    Returns the decoded string, or empty string on failure.
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        l_value = params.get("l", [""])[0]
        if not l_value:
            return ""
        # Add padding if needed
        padding = 4 - len(l_value) % 4
        if padding != 4:
            l_value += "=" * padding
        return base64.b64decode(l_value).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _is_region_or_market_url(url: str) -> bool:
    """Check if a catcar URL's decoded payload indicates a region/market selection.

    A region/market URL has region== or market== in the decoded l= param
    but does NOT have model-specific params like mod_id==, modname==, mod==,
    group==, dir1==, or st==30/40/50/70 (which indicate deeper navigation).
    """
    decoded = _decode_l_param(url)
    if not decoded:
        return False
    if "region==" not in decoded and "market==" not in decoded:
        return False
    # Exclude model-level navigation
    model_indicators = ["mod_id==", "modname==", "||mod==", "group==", "dir1=="]
    for indicator in model_indicators:
        if indicator in decoded:
            return False
    return True


def parse_year_tabs(html: str) -> list[dict]:
    """Extract year tabs from <ul class="tabs"><li><a>YYYY</a>.

    Returns list of {"year": "2018", "url": "http://..."} dicts.
    Only includes entries whose link text matches a 4-digit year pattern
    and whose URL contains 'catcar.info'.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    tabs_ul = soup.find("ul", class_="tabs")
    if not tabs_ul:
        return results

    for li in tabs_ul.find_all("li"):
        a_tag = li.find("a")
        if not a_tag:
            continue
        text = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")
        if not re.match(r"^\d{4}$", text):
            continue
        if "catcar.info" not in href:
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        results.append({"year": text, "url": href})

    return results


def parse_region_links(html: str) -> list[dict]:
    """Extract region/market links from pages.

    Finds <a> tags whose decoded URL 'l' parameter contains 'region=='
    or 'market==' (indicating a region/market selection page, not a model
    page). Excludes links inside <ul class="tabs"> (year tabs).

    Returns list of {"name": "Europe LHD", "url": "http://..."} dicts.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    # Collect all <a> tags inside <ul class="tabs"> to exclude them
    tabs_urls = set()
    tabs_ul = soup.find("ul", class_="tabs")
    if tabs_ul:
        for a_tag in tabs_ul.find_all("a"):
            href = a_tag.get("href", "")
            if href:
                tabs_urls.add(href)

    for a_tag in soup.find_all("a"):
        href = a_tag.get("href", "")
        if "catcar.info" not in href:
            continue
        if href in tabs_urls:
            continue
        if href in seen_urls:
            continue
        if not _is_region_or_market_url(href):
            continue

        name = a_tag.get_text(strip=True)
        if not name:
            continue

        seen_urls.add(href)
        results.append({"name": name, "url": href})

    return results


def parse_table_links(html: str) -> list[dict]:
    """Extract links from <td class="table__td"><a>.

    Returns list of {"name": "ACCORD", "url": "http://..."} dicts.
    Only includes links whose URL contains 'catcar.info'.
    Skips links that are region/market selection URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    for td in soup.find_all("td", class_="table__td"):
        a_tag = td.find("a")
        if not a_tag:
            continue
        href = a_tag.get("href", "")
        if "catcar.info" not in href:
            continue
        if _is_region_or_market_url(href):
            continue
        if href in seen_urls:
            continue

        name = a_tag.get_text(strip=True)
        if not name:
            continue

        seen_urls.add(href)
        results.append({"name": name, "url": href})

    return results


def parse_groups_parts_links(html: str) -> list[dict]:
    """Extract links from <a class="groups-parts__item">.

    Returns list of {"name": "ENGINE", "url": "http://..."} dicts.
    The name is taken from the <span class="groups-parts__title"> child,
    falling back to the full link text.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    for a_tag in soup.find_all("a", class_="groups-parts__item"):
        href = a_tag.get("href", "")
        if "catcar.info" not in href:
            continue
        if href in seen_urls:
            continue

        title_span = a_tag.find("span", class_="groups-parts__title")
        name = title_span.get_text(strip=True) if title_span else a_tag.get_text(strip=True)
        if not name:
            continue

        seen_urls.add(href)
        results.append({"name": name, "url": href})

    return results


def _has_parts_rows(soup: BeautifulSoup) -> bool:
    """Check if the page contains parts table rows (<tr name="POS">)."""
    return bool(soup.find("tr", attrs={"name": True}))


def detect_and_parse(html: str) -> dict:
    """Auto-detect page type and parse accordingly.

    Priority order: parts > groups_parts > years > regions > table_links

    Returns {"type": "years|regions|groups_parts|table_links|parts|empty",
             "items": [...]}
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Parts pages (highest priority)
    if _has_parts_rows(soup):
        # Delegate to the dedicated parts parser
        from crawler.parsers.parts_html import parse_parts_html
        items = parse_parts_html(html)
        if items:
            return {"type": "parts", "items": items}

    # 2. Groups-parts links
    items = parse_groups_parts_links(html)
    if items:
        return {"type": "groups_parts", "items": items}

    # 3. Year tabs
    items = parse_year_tabs(html)
    if items:
        return {"type": "years", "items": items}

    # 4. Region/market links
    items = parse_region_links(html)
    if items:
        return {"type": "regions", "items": items}

    # 5. Table links
    items = parse_table_links(html)
    if items:
        return {"type": "table_links", "items": items}

    return {"type": "empty", "items": []}
