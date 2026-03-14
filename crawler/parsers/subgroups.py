import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedSubgroup


class SubgroupsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the subgroups snapshot YAML to extract subgroup entries.

        The snapshot contains a table with rows. Each data row has cells:
        MG, Ill-No (with link), Description, Remark, Model data.

        Works with both old format (with [ref=...] [cursor=pointer]) and
        new clean ARIA snapshot format.
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        # Pattern for row lines - handles optional [ref=...] and optional quoting
        row_pattern = re.compile(
            r"(\s+)- '?row \"(.+?)\"(?:\s+\[.*?\])*'?:"
        )

        i = 0
        while i < n:
            line = lines[i]

            row_match = row_pattern.match(line)
            if row_match:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(2)

                # Skip header row (contains column headers like MG, Ill-No, Description)
                if 'MG' in row_text and 'Ill-No' in row_text:
                    i += 1
                    continue
                if 'Description' in row_text and 'Remark' in row_text and 'Model data' in row_text:
                    i += 1
                    continue

                # Parse cells within this row
                cells = []
                cell_url = None
                j = i + 1

                while j < n:
                    cell_line = lines[j]

                    # Check if we've left the row (back to same or lower indent)
                    stripped = cell_line.strip()
                    if stripped == '':
                        j += 1
                        continue
                    if stripped.startswith('#'):
                        j += 1
                        continue

                    cell_indent_match = re.match(r'(\s+)', cell_line)
                    if cell_indent_match:
                        curr_indent = len(cell_indent_match.group(1))
                        if curr_indent <= row_indent and stripped:
                            break

                    # Match cell with quoted content: cell "value" with optional [ref=...]
                    cell_match = re.match(
                        r'\s+- \'?cell "([^"]*)"(?:\s+\[.*?\])*\'?(?::\s*(.*))?',
                        cell_line
                    )
                    if cell_match:
                        cells.append(cell_match.group(1))
                        j += 1
                        continue

                    # Match empty cell: cell with optional [ref=...]
                    empty_cell_match = re.match(
                        r'\s+- \'?cell(?:\s+\[.*?\])*\'?\s*$',
                        cell_line
                    )
                    if empty_cell_match:
                        cells.append("")
                        j += 1
                        continue

                    # Capture URL from link inside Ill-No cell
                    url_match = re.match(r'\s+- /url:\s+(http://catcar\.info/.+)', cell_line)
                    if url_match and cell_url is None:
                        cell_url = url_match.group(1).strip()

                    j += 1

                # cells[0] = MG (main group number)
                # cells[1] = Ill-No
                # cells[2] = description
                # cells[3] = remark (optional)
                # cells[4] = model_data (optional)
                if len(cells) >= 3 and cell_url:
                    ill_no = cells[1].strip()
                    description = cells[2].strip()

                    if ill_no and description:
                        item = {
                            "ill_no": ill_no,
                            "description": description,
                            "url": cell_url,
                        }
                        if len(cells) > 3 and cells[3].strip():
                            item["remark"] = cells[3].strip()
                        if len(cells) > 4 and cells[4].strip():
                            item["model_data"] = cells[4].strip()
                        results.append(item)

                i = j
                continue

            i += 1

        return results

    def get_validator(self) -> type:
        return ParsedSubgroup
