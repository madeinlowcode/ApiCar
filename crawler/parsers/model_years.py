import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModelYear


class ModelYearsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the model years snapshot YAML to extract year entries.

        The snapshot contains a table with rows like:
          row "GOLF 1998 1J-W-000 001 >>" [ref=eXX]:
            - cell "GOLF" [ref=eXX]
            - cell "1998" [ref=eXX]:
              - link "1998" [ref=eXX] [cursor=pointer]:
                - /url: http://catcar.info/...
            - cell "1J-W-000 001 >>" [ref=eXX]
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        i = 0
        while i < n:
            line = lines[i]

            # Match row entries in the year table
            row_match = re.match(r'(\s+)- row "(.+)" \[ref=\w+\]:', line)
            if row_match:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(2)

                # Skip header row
                if 'Model' in row_text and 'Year' in row_text and 'Restriction' in row_text:
                    i += 1
                    continue

                # Parse cells within this row
                cells = []
                cell_url = None
                j = i + 1

                while j < n:
                    cell_line = lines[j]
                    cell_indent_match = re.match(r'(\s+)', cell_line)
                    if cell_indent_match:
                        curr_indent = len(cell_indent_match.group(1))
                        if curr_indent <= row_indent and cell_line.strip() and not cell_line.strip().startswith('#'):
                            break
                    elif cell_line.strip() == '':
                        j += 1
                        continue

                    # Match cell with content
                    cell_match = re.match(r'\s+- cell "([^"]*)" \[ref=\w+\]', cell_line)
                    if cell_match:
                        cells.append(cell_match.group(1))

                    # Match empty cells
                    empty_cell_match = re.match(r'\s+- cell \[ref=\w+\]', cell_line)
                    if empty_cell_match:
                        cells.append("")

                    # Capture URL
                    url_match = re.match(r'\s+- /url: (http://catcar\.info/.+)', cell_line)
                    if url_match and cell_url is None:
                        cell_url = url_match.group(1).strip()

                    j += 1

                # We need: model_code, year, restriction (optional)
                # cells[0] = model code (e.g. "GOLF")
                # cells[1] = year (e.g. "1998")
                # cells[2] = restriction (optional, may be empty)
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
