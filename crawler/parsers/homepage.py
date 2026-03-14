import re

from crawler.parsers.base import BaseParser
from crawler.validators.brand import ParsedBrand

# Region headings on the catcar.info homepage (Russian and English)
REGION_HEADINGS = {
    "Европа": "Europe", "Europe": "Europe",
    "Япония": "Japan", "Japan": "Japan",
    "Корея": "Korea", "Korea": "Korea",
    "США": "USA", "USA": "USA",
}

# Skip these regions entirely (aftermarket, moto, etc.)
SKIP_REGIONS = {"Общие", "General", "Multi brands"}

# Catalog paths to skip (non-brand catalogs)
SKIP_PATHS = {"/totalcatalog/", "/moto/", "/usa_oem/", "/usa_noem/", "/en/"}


class HomepageParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the homepage ARIA snapshot to extract brand name and URL pairs.

        Brands appear under region headings (Europe, Japan, Korea, USA).
        Each brand is a link inside a listitem with a catalog URL like /bmw/ or /audivw/?l=...
        """
        results = []
        seen_names = set()
        current_region = None
        skip_region = False

        lines = page_content.split('\n')
        n = len(lines)

        # Brand URLs: catalog path like /audivw/, /bmw/, /mercedes/, etc.
        # May or may not have query params
        brand_url_pattern = re.compile(r'^/[a-zA-Z][a-zA-Z0-9_-]+/')

        i = 0
        while i < n:
            line = lines[i]

            # Check for region heading (level 2 is main content, level 5 is footer)
            heading_match = re.match(r'\s*- heading "([^"]+)"', line)
            if heading_match:
                heading_text = heading_match.group(1)
                if heading_text in SKIP_REGIONS:
                    skip_region = True
                elif heading_text in REGION_HEADINGS:
                    current_region = REGION_HEADINGS[heading_text]
                    skip_region = False

            if skip_region or current_region is None:
                i += 1
                continue

            # Look for link "Name": (with or without [ref=...] [cursor=pointer])
            link_match = re.match(
                r'\s+- link "([^"]+)"(?:\s+\[.*?\])*:', line
            )
            if link_match:
                name = link_match.group(1)

                # Find /url within the next few lines
                url = None
                for j in range(i + 1, min(i + 5, n)):
                    url_match = re.match(r'\s+- /url: (.+)', lines[j])
                    if url_match:
                        candidate_url = url_match.group(1).strip()
                        if brand_url_pattern.match(candidate_url):
                            # Skip known non-brand catalog paths
                            path_match = re.match(r'^(/[a-zA-Z][a-zA-Z0-9_-]+/)', candidate_url)
                            if path_match and path_match.group(1) not in SKIP_PATHS:
                                url = candidate_url
                        break

                if url:
                    clean_name = self._extract_latin_name(name)

                    if clean_name and clean_name not in seen_names:
                        seen_names.add(clean_name)
                        path_match = re.match(r'^(/[a-zA-Z][a-zA-Z0-9_-]+/)', url)
                        catalog_path = path_match.group(1) if path_match else "/"

                        results.append({
                            "name": clean_name,
                            "url": "https://www.catcar.info" + url,
                            "region": current_region,
                            "catalog_path": catalog_path,
                        })

            i += 1

        return results

    @staticmethod
    def _is_cyrillic_word(word: str) -> bool:
        """Check if a word is primarily Cyrillic characters."""
        cyrillic_count = sum(1 for c in word if '\u0400' <= c <= '\u04FF')
        return cyrillic_count > len(word) // 2

    def _extract_latin_name(self, name: str) -> str:
        """Extract the Latin/English brand name from mixed text like 'Audi Ауди'.

        Handles special chars like ё in Citroёn by filtering out fully-Cyrillic words.
        """
        parts = name.split()
        non_cyrillic = [p for p in parts if not self._is_cyrillic_word(p)]
        if non_cyrillic:
            result = " ".join(non_cyrillic)
            # Normalize Cyrillic ё (U+0451) to Latin ë (U+00EB) in brand names
            result = result.replace('\u0451', '\u00EB').replace('\u0401', '\u00CB')
            return result
        return name

    def get_validator(self) -> type:
        return ParsedBrand
