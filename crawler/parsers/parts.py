import re

from crawler.parsers.base import BaseParser
from crawler.validators.part import ParsedPart


class PartsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the parts detail snapshot YAML to extract part entries.

        The snapshot contains a table with rows. Each data row has cells:
        position, (image placeholder), part_no (with link), description,
        remark, quantity (ST), model_data, (basket link).

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
            if not row_match:
                i += 1
                continue

            row_indent = len(row_match.group(1))
            row_text = row_match.group(2)

            # Skip header rows (contain column header keywords)
            if ('part number' in row_text.lower() or 'Part No.' in row_text) and 'Description' in row_text:
                i += 1
                continue

            # Skip subgroup description header rows (contain only description/remark/model_data, no position)
            # These are columnheader rows that describe the subgroup context

            cells = []
            cell_url = None
            j = i + 1

            while j < n:
                cell_line = lines[j]

                stripped = cell_line.strip()
                if stripped == '' or stripped.startswith('#'):
                    j += 1
                    continue

                cell_indent_match = re.match(r'(\s+)', cell_line)
                if cell_indent_match:
                    curr_indent = len(cell_indent_match.group(1))
                    if curr_indent <= row_indent and stripped:
                        break

                # Match cell with quoted content - handles optional quoting and [ref=...]
                cell_match = re.match(
                    r"\s+- '?cell \"([^\"]*)\"(?:\s+\[.*?\])*'?(?::\s*(.*))?",
                    cell_line
                )
                if cell_match:
                    cells.append(cell_match.group(1))
                    j += 1
                    continue

                # Match empty cell
                empty_cell_match = re.match(
                    r"\s+- '?cell(?:\s+\[.*?\])*'?\s*$",
                    cell_line
                )
                if empty_cell_match:
                    cells.append("")
                    j += 1
                    continue

                # Capture URL from tradesoft or any http URL in links
                url_match = re.match(r'\s+- /url:\s+(http\S+)', cell_line)
                if url_match and cell_url is None:
                    # Skip "Add to Basket" URLs - we want the part number link URL
                    candidate_url = url_match.group(1).strip()
                    cell_url = candidate_url

                j += 1

            # The parts table has these cells (with image placeholder and basket):
            # cells[0] = position
            # cells[1] = empty (image placeholder)
            # cells[2] = part_no
            # cells[3] = description (may have "additionally to be used items: N")
            # cells[4] = remark (may be empty)
            # cells[5] = quantity (ST)
            # cells[6] = model_data
            # cells[7] = "Add to Basket"

            # Check if this is a columnheader-only row (subgroup header)
            # by checking if the row has columnheader children instead of cell children
            if len(cells) >= 3 and cell_url:
                position_str = cells[0].strip()
                part_no = cells[2].strip() if len(cells) > 2 else ""

                if part_no and position_str.isdigit():
                    # Description: strip "additionally to be used items: N" suffix
                    raw_desc = cells[3].strip() if len(cells) > 3 else ""
                    desc = re.sub(r'\s*additionally to be used items:.*$', '', raw_desc).strip()
                    # Strip trailing " -"
                    desc = re.sub(r'\s*-\s*$', '', desc).strip()

                    remark = cells[4].strip() if len(cells) > 4 else ""
                    quantity_str = cells[5].strip() if len(cells) > 5 else ""
                    model_data = cells[6].strip() if len(cells) > 6 else ""

                    if part_no and desc:
                        item = {
                            "part_no": part_no,
                            "description": desc,
                            "url": cell_url,
                            "position": position_str,
                        }
                        if remark:
                            item["remark"] = remark
                        if quantity_str.isdigit():
                            item["quantity"] = quantity_str
                        if model_data and model_data != "Add to Basket":
                            item["model_data"] = model_data
                        results.append(item)

            i = j if j > i else i + 1
            continue

        return results

    def get_validator(self) -> type:
        return ParsedPart
