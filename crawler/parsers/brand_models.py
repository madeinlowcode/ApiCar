import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedModel


class BrandModelsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the brand models snapshot YAML to extract model information.

        The snapshot contains a table with rows like:
          row "CODE ModelName Description ProductionDate Markets" [ref=eXX]:
            - cell "CODE" [ref=eXX]
            - cell "ModelName" [ref=eXX]:
              - link "ModelName" [ref=eXX] [cursor=pointer]:
                - /url: http://catcar.info/...
            - cell "Description" (optional)
            - cell "ProductionDate" [ref=eXX]
            - cell "Markets" [ref=eXX]
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        i = 0
        while i < n:
            line = lines[i]

            # Match data rows in the model table
            # Row pattern: row "CODE ModelName ... ProductionDate Markets"
            # We identify data rows by looking for cell structures
            # A data row starts with: - row "..."
            row_match = re.match(r'(\s+)- row "(.+)" \[ref=\w+\]:', line)
            if row_match:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(2)

                # Skip header row
                if 'Catalog' in row_text and 'Model' in row_text and 'Production date' in row_text:
                    i += 1
                    continue

                # Parse cells within this row
                cells = []
                cell_url = None
                j = i + 1

                while j < n:
                    cell_line = lines[j]
                    # Check if we've left the row's scope by checking indent
                    cell_indent_match = re.match(r'(\s+)', cell_line)
                    if cell_indent_match:
                        curr_indent = len(cell_indent_match.group(1))
                        if curr_indent <= row_indent and cell_line.strip() and not cell_line.strip().startswith('#'):
                            break
                    elif cell_line.strip() == '':
                        j += 1
                        continue

                    # Match cell content
                    cell_match = re.match(r'\s+- cell "([^"]*)" \[ref=\w+\]', cell_line)
                    if cell_match:
                        cells.append(cell_match.group(1))

                    # Also match empty cells
                    empty_cell_match = re.match(r'\s+- cell \[ref=\w+\]', cell_line)
                    if empty_cell_match:
                        cells.append("")

                    # Capture URL from link inside cell
                    url_match = re.match(r'\s+- /url: (http://catcar\.info/.+)', cell_line)
                    if url_match and cell_url is None:
                        cell_url = url_match.group(1).strip()

                    j += 1

                # We need at least: code, name, production_date
                # Typical row: [code, name, description_or_empty, prod_date, markets]
                if len(cells) >= 4 and cell_url:
                    code = cells[0].strip()
                    name = cells[1].strip()
                    # cells[2] is description (may be empty)
                    # cells[3] is production_date
                    # cells[4] is markets (if present)

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
