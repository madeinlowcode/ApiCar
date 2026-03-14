import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModelYear

# Regex fragments that make [ref=...] and [cursor=pointer] optional
_ATTRS = r'(?:\s+\[.*?\])*'


class ModelYearsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the model years snapshot YAML to extract year entries.

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
        url_re = re.compile(r'^\s+- /url:\s+(http\S+)')

        # Header keywords to skip
        header_keywords = {'Model', 'Year', 'Restriction',
                           'Модель', 'Год', 'Ограничение'}

        i = 0
        while i < n:
            line = lines[i]

            row_match = row_re.match(line)
            if row_match:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(2)

                # Skip header row
                row_words = set(row_text.split())
                if len(row_words & header_keywords) >= 2:
                    i += 1
                    continue

                # Parse cells within this row
                cells = []
                cell_url = None
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
                        break

                    # Match cell with content
                    cm = cell_re.match(cell_line)
                    if cm:
                        cells.append(cm.group(1))
                        j += 1
                        continue

                    # Match empty cell
                    ecm = empty_cell_re.match(cell_line)
                    if ecm:
                        cells.append("")
                        j += 1
                        continue

                    # Match URL
                    um = url_re.match(cell_line)
                    if um and cell_url is None:
                        cell_url = um.group(1).strip()

                    j += 1

                # cells: [model_code, year, restriction(optional)]
                if len(cells) >= 2 and cell_url:
                    year_str = cells[1].strip()
                    if year_str.isdigit():
                        restriction = cells[2].strip() if len(cells) > 2 else ""
                        item = {
                            "year": int(year_str),
                            "url": cell_url,
                        }
                        if restriction:
                            item["restriction"] = restriction
                        results.append(item)

                i = j
                continue

            i += 1

        return results

    def get_validator(self) -> type:
        return ParsedModelYear
