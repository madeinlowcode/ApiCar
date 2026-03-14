import re

from crawler.parsers.base import BaseParser
from crawler.validators.brand import ParsedBrand


class HomepageParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the homepage snapshot YAML to extract brand name and URL pairs.

        The snapshot is a Playwright accessibility tree in YAML format.
        Brand entries look like:
            - link "BrandName" [ref=eXX] [cursor=pointer]:
              - /url: /some-path/?lang=en
        """
        results = []
        seen = set()

        # Match link entries with brand names that have a /url child
        # Pattern: link "Name" ... followed by /url: path
        # We scan line by line looking for link + url pairs in listitem context
        lines = page_content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for a link with a quoted name that has cursor=pointer
            link_match = re.match(
                r'\s+- link "([^"]+)" \[ref=\w+\] \[cursor=pointer\]:', line
            )
            if link_match:
                name = link_match.group(1)
                # Look for the /url on the next line(s) (within next few lines)
                for j in range(i + 1, min(i + 5, len(lines))):
                    url_match = re.match(r'\s+- /url: (.+)', lines[j])
                    if url_match:
                        url = url_match.group(1).strip()
                        # Filter: only include brand links (skip navigation, news links etc.)
                        # Brand links are in listitem context and link to catalog paths
                        # We identify brands by looking at their context
                        # Skip links that are clearly not brands
                        key = (name, url)
                        if key not in seen:
                            seen.add(key)
                        break
            i += 1

        # Better approach: find all listitem -> link -> /url patterns
        # that are in the main brand grid section
        # The brands appear in list/listitem structures in the main content
        results = self._extract_brands(page_content)
        return results

    def _extract_brands(self, content: str) -> list[dict]:
        """Extract brands from the main brand listing section."""
        results = []
        seen_names = set()

        lines = content.split('\n')
        n = len(lines)

        # We look for listitem blocks containing a link with cursor=pointer
        # that has a /url child pointing to a catalog path
        # Brand URLs match: /brandname/?lang=en or /brandname/?lang=en&l=...
        # They do NOT match: /en/, /setlang.php, "#?utm...", https://www...

        brand_url_pattern = re.compile(
            r'^/[a-zA-Z][a-zA-Z0-9_-]+/\?'
        )

        i = 0
        while i < n:
            line = lines[i]
            # Look for link "Name" with cursor=pointer
            link_match = re.match(
                r'(\s+)- link "([^"]+)" \[ref=\w+\] \[cursor=pointer\]:', line
            )
            if link_match:
                indent = len(link_match.group(1))
                name = link_match.group(2)

                # Find /url within the next few lines at deeper indent
                url = None
                for j in range(i + 1, min(i + 4, n)):
                    url_match = re.match(r'\s+- /url: (.+)', lines[j])
                    if url_match:
                        candidate_url = url_match.group(1).strip()
                        if brand_url_pattern.match(candidate_url):
                            url = candidate_url
                        break

                if url and name not in seen_names:
                    # Skip non-brand links (multi-brand catalog entries, etc.)
                    # Multi-brand names contain "Aftermarket", "Genuine", "parts"
                    skip_keywords = [
                        "CATCAR Aftermarket", "Genuine USA parts",
                        "Aftermarket USA parts", "Connect CatCar catalogs",
                        "On-line car parts catalogs",
                        "Read more",
                    ]
                    if name not in skip_keywords:
                        seen_names.add(name)
                        results.append({"name": name, "url": url})

            i += 1

        return results

    def get_validator(self) -> type:
        return ParsedBrand
