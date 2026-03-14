import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModel

# Regex fragments that make [ref=...] and [cursor=pointer] optional
_ATTRS = r'(?:\s+\[.*?\])*'


class BrandModelsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the brand models snapshot YAML to extract model information.

        Supports both old format (with [ref=eXX] [cursor=pointer]) and
        new clean ARIA snapshot format (without those attributes).
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

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

                # Expected cells: [code, name, description(maybe empty), prod_date, markets]
                if len(cells) >= 4 and cell_url:
                    code = cells[0].strip()
                    name = cells[1].strip()
                    description = cells[2].strip() if len(cells) > 2 else ""
                    prod_date = cells[3].strip() if len(cells) > 3 else ""
                    markets = cells[4].strip() if len(cells) > 4 else ""

                    if code and name and prod_date and cell_url:
                        item = {
                            "code": code,
                            "name": name,
                            "url": cell_url,
                            "production_date": prod_date,
                        }
                        if description:
                            item["description"] = description
                        if markets:
                            item["markets"] = markets
                        results.append(item)

                i = j
                continue

            i += 1

        return results

    def get_validator(self) -> type:
        return ParsedModel
