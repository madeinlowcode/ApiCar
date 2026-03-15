"""Parser for catalog pages that show market/region selection first (Toyota, Hyundai).

These pages list markets (Europe, Japan, USA, etc.) as links.
Each market link leads to a models page (which can be parsed by LinkModelsParser or BrandModelsParser).

Returns a list of market entries with URLs — the engine enqueues these as additional level-2 items.
"""
import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModel


# Known market names
KNOWN_MARKETS = {
    "Europe", "USA", "Japan", "Middle East", "Asia",
    "General", "Australia", "Canada", "Korea",
}


class MarketSelectionParser(BaseParser):
    async def parse(self, page_content: str, page_url: str = "") -> list[dict]:
        """Parse market selection page.

        Returns empty list for models (markets are not models).
        The engine should use extract_market_links() to get the market URLs.
        """
        # This page type has no models — only market links
        return []

    def extract_market_links(self, content: str) -> list[dict]:
        """Extract market links from the selection page.

        Returns list of dicts with 'name' and 'url' for each market.
        """
        results = []
        lines = content.split('\n')
        n = len(lines)

        link_re = re.compile(r'\s*- link "([^"]+)"(?:\s+\[.*?\])*:')
        url_re = re.compile(r'\s+- /url:\s+(https?://\S+)')

        for i in range(n):
            m = link_re.match(lines[i])
            if not m:
                continue

            name = m.group(1).strip()

            # Check if it's a known market name
            if name not in KNOWN_MARKETS:
                continue

            # Find URL in next few lines
            for j in range(i + 1, min(i + 5, n)):
                url_m = url_re.match(lines[j])
                if url_m and 'catcar.info' in url_m.group(1):
                    results.append({
                        "name": name,
                        "url": url_m.group(1).strip(),
                    })
                    break

        return results

    def get_validator(self) -> type:
        return ParsedModel
