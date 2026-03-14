import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedCategory


class CategoriesParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the categories (main parts) snapshot YAML.

        Categories appear as links with an img child and a /url child pointing
        to catcar.info. The link text has the category name duplicated, e.g.
        "Engine Engine". Works with both old format (with [ref=...]) and new
        clean ARIA snapshot format.
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        # Pattern for category links: link text has "Name Name" pattern
        # Handle both old format with [ref=eXX] [cursor=pointer] and new clean format
        link_pattern = re.compile(
            r'\s+- link "(.+?)"(?:\s+\[.*?\])*:'
        )

        i = 0
        while i < n:
            line = lines[i]
            link_match = link_pattern.match(line)
            if link_match:
                link_text = link_match.group(1)

                # Look ahead for /url and img children within the next few lines
                url = None
                has_img = False
                for j in range(i + 1, min(i + 6, n)):
                    child = lines[j]
                    # Check for /url pointing to catcar.info
                    url_match = re.match(r'\s+- /url:\s+(http://catcar\.info/.+)', child)
                    if url_match:
                        url = url_match.group(1).strip()
                    # Check for img child (with or without attributes)
                    if re.match(r'\s+- img\b', child):
                        has_img = True
                    # Stop if we hit another top-level sibling (same or lower indent)
                    if j > i + 1 and re.match(r'\s+- (?:link|heading|table|generic\b)', child):
                        # Check indent - if same level as original link, stop
                        link_indent = len(line) - len(line.lstrip())
                        child_indent = len(child) - len(child.lstrip())
                        if child_indent <= link_indent:
                            break

                if url and has_img:
                    # Extract unique name from duplicated text like "Engine Engine"
                    # Try splitting: if the text is "X X" where both halves match, take one
                    name = self._extract_unique_name(link_text)
                    results.append({"name": name, "url": url})

            i += 1

        return results

    @staticmethod
    def _extract_unique_name(link_text: str) -> str:
        """
        Extract the unique category name from potentially duplicated link text.
        E.g. "Engine Engine" -> "Engine", "Fuel, exhaust, cooling Fuel, exhaust, cooling" -> "Fuel, exhaust, cooling"
        """
        text = link_text.strip()
        # Try to find a split point where both halves are identical
        length = len(text)
        for mid in range(1, length):
            if text[mid] == ' ':
                left = text[:mid]
                right = text[mid + 1:]
                if left == right:
                    return left
        return text

    def get_validator(self) -> type:
        return ParsedCategory
