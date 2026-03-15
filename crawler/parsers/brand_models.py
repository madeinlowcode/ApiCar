import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModel

# Regex fragments that make [ref=...] and [cursor=pointer] optional
_ATTRS = r'(?:\s+\[.*?\])*'


class BrandModelsParser(BaseParser):
    async def parse(self, page_content: str, page_url: str = "") -> list[dict]:
        """
        Parse the brand models snapshot YAML to extract model information.

        Supports both old format (with [ref=eXX] [cursor=pointer]) and
        new clean ARIA snapshot format (without those attributes).

        Args:
            page_content: ARIA snapshot text
            page_url: The URL of the page (used to detect active market)
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        # Detect active market — prefer URL-based detection, fall back to tab-based
        market_name = self._detect_market_from_url(page_url) or self._detect_market(page_content)

        # Patterns flexible for both old and new snapshot formats
        row_re = re.compile(r'^(\s+)- row "(.+?)"' + _ATTRS + r':')
        cell_re = re.compile(r'^\s+- cell "([^"]*)"' + _ATTRS)
        empty_cell_re = re.compile(r'^\s+- cell' + _ATTRS + r'\s*$')
        link_re = re.compile(r'^\s+- link "([^"]*)"' + _ATTRS)
        url_re = re.compile(r'^\s+- /url:\s+(http\S+)')

        # Header keywords to skip
        header_keywords = {'Catalog', 'Model', 'Production date', 'Production',
                           'Каталог', 'Модель', 'Дата производства', 'Производство'}

        i = 0
        while i < n:
            line = lines[i]

            row_match = row_re.match(line)
            if row_match:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(2)

                # Skip header row: check if row text contains multiple header keywords
                row_words = set(row_text.split())
                if len(row_words & header_keywords) >= 2:
                    i += 1
                    continue

                # Parse cells within this row
                cells = []
                cell_url = None
                link_name = None
                j = i + 1

                while j < n:
                    cell_line = lines[j]

                    if cell_line.strip() == '':
                        j += 1
                        continue

                    # Check indentation to see if we've left the row
                    indent_match = re.match(r'^(\s+)', cell_line)
                    if indent_match:
                        curr_indent = len(indent_match.group(1))
                        if curr_indent <= row_indent:
                            break
                    else:
                        # Non-indented line means we've left
                        break

                    # Match cell with content
                    cm = cell_re.match(cell_line)
                    if cm:
                        cells.append(cm.group(1))
                        j += 1
                        continue

                    # Match empty cell (no quotes)
                    ecm = empty_cell_re.match(cell_line)
                    if ecm:
                        cells.append("")
                        j += 1
                        continue

                    # Match link inside cell
                    lm = link_re.match(cell_line)
                    if lm:
                        link_name = lm.group(1)

                    # Match URL
                    um = url_re.match(cell_line)
                    if um and cell_url is None:
                        cell_url = um.group(1).strip()

                    j += 1

                # Two table formats:
                # VW-style (5+ cells): [code, name, description, prod_date, markets]
                # Toyota-style (4 cells): [code, name, prod_date, production_codes]
                if len(cells) >= 4 and cell_url:
                    code = cells[0].strip()
                    name = cells[1].strip()

                    if len(cells) == 4:
                        # Toyota-style: code, name, prod_date, production_codes
                        description = ""
                        prod_date = cells[2].strip()
                        markets = ""
                        production_codes = cells[3].strip()
                    else:
                        # VW-style: code, name, description, prod_date, markets
                        description = cells[2].strip()
                        prod_date = cells[3].strip()
                        markets = cells[4].strip() if len(cells) > 4 else ""
                        production_codes = ""

                    if code and name and prod_date and cell_url:
                        item = {
                            "code": code,
                            "name": name,
                            "url": cell_url,
                            "production_date": prod_date,
                            "market": market_name,
                        }
                        if description:
                            item["description"] = description
                        if markets:
                            item["markets"] = markets
                        if production_codes:
                            item["production_codes"] = production_codes
                        results.append(item)

                i = j
                continue

            i += 1

        return results

    @staticmethod
    def _detect_market_from_url(url: str) -> str | None:
        """Extract market name from the base64-encoded 'l' URL parameter.

        The 'l' param decodes to something like:
            sts==>{"10":"...","20":"VW"}||st==20||brand==vw||market==USA
        We extract the value after 'market=='.
        """
        if not url:
            return None
        import base64
        from urllib.parse import urlparse, parse_qs

        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            l_param = params.get("l", [None])[0]
            if not l_param:
                return None
            # Add padding if needed
            padding = 4 - len(l_param) % 4
            if padding != 4:
                l_param += "=" * padding
            decoded = base64.b64decode(l_param).decode("utf-8", errors="ignore")
            # Look for market==XXX pattern
            for part in decoded.split("||"):
                if part.startswith("market=="):
                    code = part.split("==", 1)[1]
                    return {
                        "RDW": "Europe", "ZA": "South Africa", "USA": "USA",
                        "RA": "Argentina", "MEX": "Mexico", "CN": "China (FAW-VW)",
                        "SVW": "China (SVW)", "BR": "Brazil",
                    }.get(code, code)
        except Exception:
            return None
        return None

    def _detect_market(self, content: str) -> str:
        """Detect the active market name from market tab links.

        Market tabs appear as links in a list before the models table:
          - link "EUROPE": ...
          - link "USA": ...

        The tab names may be in English or Russian. We map known Russian names.
        """
        russian_to_english = {
            "ЕВРОПА": "Europe", "EUROPE": "Europe",
            "США": "USA", "USA": "USA",
            "ЮЖНАЯ АФРИКА": "South Africa", "SOUTH AFRICA": "South Africa",
            "АРГЕНТИНА": "Argentina", "ARGENTINA": "Argentina",
            "МЕКСИКА": "Mexico", "MEXICO": "Mexico",
            "БРАЗИЛИЯ": "Brazil", "BRAZIL": "Brazil",
            "КИТАЙ (FAW-VW)": "China (FAW-VW)", "CHINA (FAW-VW)": "China (FAW-VW)",
            "КИТАЙ (SVW)": "China (SVW)", "CHINA (SVW)": "China (SVW)",
        }

        # Look for market tab links. The first one that appears as a link
        # is typically the active market (the page shows its models).
        market_link_re = re.compile(r'^\s+- link "([^"]+)"' + _ATTRS + r':')
        url_re_local = re.compile(r'^\s+- /url:\s+http\S+')

        lines = content.split('\n')
        found_markets = []
        for i, line in enumerate(lines):
            m = market_link_re.match(line)
            if m:
                name = m.group(1).strip()
                # Check if the next line has a catcar URL (market tabs point to catcar)
                if i + 1 < len(lines) and url_re_local.match(lines[i + 1]):
                    if name.upper() in russian_to_english:
                        found_markets.append(russian_to_english[name.upper()])
                    elif name.upper() in {v.upper() for v in russian_to_english.values()}:
                        found_markets.append(name)

        # The first market found is usually the active/default one
        return found_markets[0] if found_markets else "Europe"

    def extract_market_tabs(self, content: str) -> list[dict]:
        """Extract all market tab links from a brand page.

        Returns list of dicts with 'name' and 'url' for each market tab.
        Used by the engine to enqueue additional level-2 URLs for all markets.
        """
        market_link_re = re.compile(r'^\s+- link "([^"]+)"' + _ATTRS + r':')
        url_re_local = re.compile(r'^\s+- /url:\s+(http\S+)')

        # Known market names (English only — page is loaded with ?lang=en)
        known_markets = {
            "Europe", "South Africa", "USA", "Argentina", "Mexico",
            "Brazil", "FAW-VW", "SVW", "China", "India",
        }

        lines = content.split('\n')
        tabs = []
        for i, line in enumerate(lines):
            m = market_link_re.match(line)
            if m:
                name = m.group(1).strip()
                if name in known_markets and i + 1 < len(lines):
                    url_m = url_re_local.match(lines[i + 1])
                    if url_m:
                        tabs.append({"name": name, "url": url_m.group(1).strip()})
        return tabs

    def get_validator(self) -> type:
        return ParsedModel
