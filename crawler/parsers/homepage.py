import re

from crawler.parsers.base import BaseParser
from crawler.validators.brand import ParsedBrand

# Region headings on the catcar.info homepage (may appear in Russian or English)
REGION_HEADINGS = {
    "Европа": "Europe", "Europe": "Europe",
    "Япония": "Japan", "Japan": "Japan",
    "Корея": "Korea", "Korea": "Korea",
    "США": "USA", "USA": "USA",
    "Общие": "General", "Multi brands": "General",
}

# Skip these link names — they are not car brands
SKIP_NAMES = {
    "CATCAR Aftermarket", "Genuine USA parts", "Aftermarket USA parts",
    "Connect CatCar catalogs", "On-line car parts catalogs", "Read more",
    "CATCAR Moto Parts",
}


class HomepageParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the homepage ARIA snapshot to extract brand name and URL pairs.

        The ARIA snapshot format from Playwright:
            - link "BrandName":
              - /url: /path/?l=...

        Brands are inside listitem elements under region headings.
        """
        results = []
        seen_names = set()
        current_region = "Europe"

        lines = page_content.split('\n')
        n = len(lines)

        # Brand URLs match catalog paths like /audivw/?l=... or /bmw/?l=...
        brand_url_pattern = re.compile(r'^/[a-zA-Z][a-zA-Z0-9_-]+/\?')

        i = 0
        while i < n:
            line = lines[i]

            # Check for region heading
            heading_match = re.match(r'\s*- heading "([^"]+)"', line)
            if heading_match:
                heading_text = heading_match.group(1)
                if heading_text in REGION_HEADINGS:
                    current_region = REGION_HEADINGS[heading_text]

            # Look for link "Name": (with or without [ref=...] [cursor=pointer])
            link_match = re.match(
                r'(\s+)- link "([^"]+)"(?:\s+\[.*?\])*:', line
            )
            if link_match:
                name = link_match.group(2)

                # Find /url within the next few lines
                url = None
                for j in range(i + 1, min(i + 5, n)):
                    url_match = re.match(r'\s+- /url: (.+)', lines[j])
                    if url_match:
                        candidate_url = url_match.group(1).strip()
                        if brand_url_pattern.match(candidate_url):
                            url = candidate_url
                        break

                if url and name not in seen_names:
                    # Extract just the brand name (remove Russian/other translations)
                    # Format: "Audi Ауди" -> "Audi" or "Volkswagen Фольксваген" -> "Volkswagen"
                    clean_name = self._extract_latin_name(name)

                    if clean_name and clean_name not in SKIP_NAMES and clean_name not in seen_names:
                        seen_names.add(clean_name)
                        # Extract catalog path from URL
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

    def _extract_latin_name(self, name: str) -> str:
        """Extract the Latin/English brand name from mixed text like 'Audi Ауди'."""
        # Split and take parts that are ASCII/Latin
        parts = name.split()
        latin_parts = [p for p in parts if all(c.isascii() for c in p)]
        if latin_parts:
            return " ".join(latin_parts)
        # If no Latin parts, return original (some brands may have only non-Latin)
        return name

    def get_validator(self) -> type:
        return ParsedBrand
