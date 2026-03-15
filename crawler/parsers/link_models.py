"""Parser for catalog pages that show models as image links (Ford, Opel, Renault, etc.).

These pages show a grid of model cards, each being a link with an image and text.
The link text contains model name, code, and production dates.

Examples:
  Ford:  link "B-Max CB2 2012-" → img "B-Max CB2 2012-"
  Opel:  link "M13 ADAM M13 ADAM ( 2013 - )" → img "M13 ADAM", text "M13 ADAM ( 2013 - )"
"""
import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModel


# Known link texts to skip (not real models)
SKIP_NAMES = {
    "Accessories", "accessories", "Zubehör",
    "Motorcycle", "Motorcycle Classic",
    # Sub-brand tabs (Opel/Vauxhall)
    "Opel", "Vauxhall",
    # Breadcrumb items (BMW)
    "Marque", "Region",
}

# Patterns to filter out non-model links
_FOOTER_RE = re.compile(r'^\d{4}\s+CATCAR', re.IGNORECASE)

# Regex to find year ranges like "2012-", "1998-2000", "( 2013 - )", "( 2000 - 2008)"
_YEAR_RANGE_RE = re.compile(
    r'\(?\s*(\d{4})\s*-\s*(\d{4})?\s*\)?'
)

# Regex for code-first format: "M13 ADAM" or "H00 AGILA-A"
_CODE_FIRST_RE = re.compile(
    r'^([A-Z]\d{2,3})\s+(.+)$'
)

# Regex for name-first format: "B-Max CB2 2012-" or "Cougar MC 1998-2000"
_NAME_FIRST_RE = re.compile(
    r'^(.+?)\s+([A-Z]{2,}[A-Z0-9]*)\s+(\d{4}.*)$'
)


class LinkModelsParser(BaseParser):
    async def parse(self, page_content: str, page_url: str = "") -> list[dict]:
        """Parse link-style model pages.

        Extracts model name, code, production date, and URL from image links.
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        # Detect market tabs (Opel has Opel/Vauxhall tabs)
        market_name = self._detect_market(page_content, page_url)

        i = 0
        while i < n:
            line = lines[i]

            # Match link with content (has a colon at end = has children)
            link_match = re.match(
                r'(\s*)- link "([^"]+)"(?:\s+\[.*?\])*:',
                line
            )
            if not link_match:
                i += 1
                continue

            link_indent = len(link_match.group(1))
            link_text = link_match.group(2)

            # Scan children for /url and img
            url = None
            img_text = None
            child_text = None
            j = i + 1

            while j < n:
                child = lines[j]
                if child.strip() == '':
                    j += 1
                    continue

                # Check indent — stop if same or lower
                indent_m = re.match(r'^(\s+)', child)
                if indent_m:
                    if len(indent_m.group(1)) <= link_indent:
                        break
                else:
                    break

                # URL
                url_m = re.match(r'\s+- /url:\s+(https?://\S+)', child)
                if url_m and url is None:
                    url = url_m.group(1).strip()

                # Image text
                img_m = re.match(r'\s+- img "([^"]+)"', child)
                if img_m:
                    img_text = img_m.group(1).strip()

                # Text node
                text_m = re.match(r'\s+- text:\s+(.+)', child)
                if text_m:
                    child_text = text_m.group(1).strip()

                j += 1

            # Need at least a catcar URL
            if not url or 'catcar.info' not in url:
                i = j
                continue

            # Use image text as primary source, fall back to link text
            primary_text = img_text or link_text
            # For dates, prefer the child text (Opel puts dates in text node)
            date_source = child_text or link_text

            # Skip non-model links
            if primary_text in SKIP_NAMES:
                i = j
                continue

            # Skip known UI/navigation links and footer
            if primary_text in {"Русский", "English", "Connect CatCar catalogs",
                                "Connect catalogs", "Check"}:
                i = j
                continue
            if _FOOTER_RE.match(primary_text):
                i = j
                continue

            # Parse the model info
            parsed = self._parse_model_text(primary_text, date_source)
            if parsed:
                item = {
                    "code": parsed["code"],
                    "name": parsed["name"],
                    "url": url,
                    "production_date": parsed["production_date"],
                    "market": market_name,
                }
                results.append(item)

            i = j

        return results

    def _parse_model_text(self, img_text: str, full_text: str) -> dict | None:
        """Extract code, name, and production date from model text.

        Handles two formats:
          Code-first: "M13 ADAM" (Opel) — dates in full_text as "( 2013 - )"
          Name-first: "B-Max CB2 2012-" (Ford) — all in one string
        """
        code = ""
        name = ""
        production_date = ""

        # Try code-first format: "M13 ADAM", "H00 AGILA-A"
        code_first = _CODE_FIRST_RE.match(img_text)
        if code_first:
            code = code_first.group(1)
            name = code_first.group(2).strip()
            # Extract date from full text (Opel format: "M13 ADAM ( 2013 - )")
            year_match = _YEAR_RANGE_RE.search(full_text)
            if year_match:
                start = year_match.group(1)
                end = year_match.group(2)
                production_date = f"{start}-{end}" if end else f"{start}-"
            else:
                production_date = ""
        else:
            # Try name-first format: "B-Max CB2 2012-", "Cougar MC 1998-2000"
            name_first = _NAME_FIRST_RE.match(img_text)
            if name_first:
                name = name_first.group(1).strip()
                code = name_first.group(2)
                production_date = name_first.group(3).strip()
            else:
                # Fallback: just use the whole text as name, try to find year
                year_match = _YEAR_RANGE_RE.search(full_text)
                if year_match:
                    # Remove year part from name
                    name = _YEAR_RANGE_RE.sub('', img_text).strip()
                    start = year_match.group(1)
                    end = year_match.group(2)
                    production_date = f"{start}-{end}" if end else f"{start}-"
                else:
                    name = img_text.strip()

                # Try to extract code from name
                parts = name.split()
                if len(parts) >= 2:
                    # Check if last word looks like a code (all uppercase, 2-5 chars)
                    candidate = parts[-1]
                    if re.match(r'^[A-Z][A-Z0-9]{1,4}$', candidate):
                        code = candidate
                        name = ' '.join(parts[:-1])
                    elif re.match(r'^[A-Z][A-Z0-9]{1,4}$', parts[0]):
                        code = parts[0]
                        name = ' '.join(parts[1:])

                if not code:
                    # Use name as code (simple catalogs like Renault)
                    code = re.sub(r'[^A-Za-z0-9 -]', '', name).strip()[:20] or name[:20]

        if not name:
            return None

        return {
            "code": code,
            "name": name,
            "production_date": production_date or "unknown",
        }

    def _detect_market(self, content: str, page_url: str) -> str:
        """Detect market from page content or URL."""
        # Check URL for market hints
        if page_url:
            lower_url = page_url.lower()
            if 'usa' in lower_url:
                return "USA"
            if 'brazil' in lower_url or 'br' in lower_url:
                return "Brazil"

        # Check for market tabs in content (Opel has Opel/Vauxhall)
        if 'Vauxhall' in content:
            # If we're on the Opel page, default market is Opel (Europe)
            return "Europe"

        return "Europe"

    def extract_market_tabs(self, content: str) -> list[dict]:
        """Extract market/brand tabs (e.g. Opel/Vauxhall switch)."""
        tabs = []
        lines = content.split('\n')
        # Look for list with links to the same catalog (sub-brand tabs)
        link_re = re.compile(r'\s+- link "([^"]+)"(?:\s+\[.*?\])*:')
        url_re = re.compile(r'\s+- /url:\s+(https?://\S+catcar\.info/\S+)')

        for i, line in enumerate(lines):
            m = link_re.match(line)
            if m:
                name = m.group(1).strip()
                if name in {"Opel", "Vauxhall"} and i + 1 < len(lines):
                    url_m = url_re.match(lines[i + 1])
                    if url_m:
                        tabs.append({"name": name, "url": url_m.group(1).strip()})
        return tabs

    def get_validator(self) -> type:
        return ParsedModel
