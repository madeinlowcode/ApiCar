import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedCategory


class CategoriesParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the categories (main parts) snapshot YAML.

        The snapshot has links like:
          link "CategoryName CategoryName" [ref=eXX] [cursor=pointer]:
            - /url: http://catcar.info/audivw/?lang=en&l=...MainGroup==N
            - img "CategoryName" [ref=eXX]
            - generic [ref=eXX]: CategoryName

        The 10 categories appear in a generic container. Each link has
        the category name duplicated in the link text.
        """
        results = []

        # The category names we expect (in order)
        expected_categories = [
            "Accessors",
            "Engine",
            "Fuel, exhaust, cooling",
            "Gearbox",
            "Front axle, steering",
            "Rear axle",
            "Wheels, brakes",
            "Pedals",
            "Body",
            "Electrics",
        ]

        lines = page_content.split('\n')
        n = len(lines)

        for cat_name in expected_categories:
            # Search for the link containing this category name
            for i in range(n):
                line = lines[i]
                # The link text contains the category name twice: "Name Name"
                double_name = f'{cat_name} {cat_name}'
                link_match = re.match(
                    r'\s+- link "' + re.escape(double_name) + r'" \[ref=\w+\] \[cursor=pointer\]:',
                    line
                )
                if link_match:
                    # Find the /url in the next few lines
                    for j in range(i + 1, min(i + 5, n)):
                        url_match = re.match(r'\s+- /url: (http://catcar\.info/.+)', lines[j])
                        if url_match:
                            url = url_match.group(1).strip()
                            results.append({"name": cat_name, "url": url})
                            break
                    break

        return results

    def get_validator(self) -> type:
        return ParsedCategory
