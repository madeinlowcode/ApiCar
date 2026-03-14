import re

from crawler.parsers.base import BaseParser
from crawler.validators.part import ParsedPart


class PartsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the parts detail snapshot YAML to extract part entries.

        The snapshot contains a table with rows like:
          row "1 04C100032F base engine ... 1 PR-G1C Add to Basket" [ref=eXX]:
            - cell "1" [ref=eXX]      <- position
            - cell [ref=eXX]          <- image (empty)
            - cell "04C100032F" [ref=eXX]:
              - link "04C100032F" [ref=eXX] [cursor=pointer]:
                - /url: http://ar-demo.tradesoft.pro/search.html?article=04C100032F...
            - cell "base engine ..." [ref=eXX]:  <- description
            - cell "remark" [ref=eXX]  <- remark (may be empty)
            - cell "1" [ref=eXX]       <- quantity (ST)
            - cell "PR-G1C" [ref=eXX]  <- model_data
            - cell "Add to Basket" [ref=eXX]  <- basket
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        i = 0
        while i < n:
            line = lines[i]

            # Match row entries - use single or double quotes pattern
            row_match = re.match(r"(\s+)- ('?)row \"(.+?)\" \[ref=\w+\]\2:", line)
            if not row_match:
                # Try the quoted row format: - 'row "..." [ref=eXX]':
                row_match = re.match(r"(\s+)- 'row \"(.+)\" \[ref=\w+\]':", line)
                if row_match:
                    row_indent = len(row_match.group(1))
                    row_text = row_match.group(2)
                else:
                    i += 1
                    continue
            else:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(3)

            # Skip header rows
            if 'part number' in row_text or 'Description' in row_text:
                i += 1
                continue

            # Also skip subgroup info rows (no part number pattern)
            # Part rows start with a position number and contain part_no
            # Skip rows that are subgroup headers (description rows without position number)
            # The subgroup header row has format: "description remark model_data"
            # without leading position number

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

                # Match cell with quoted content
                cell_match = re.match(r"\s+- ('?)cell \"([^\"]*)\"\s*(\[ref=\w+\])?\1", cell_line)
                if cell_match:
                    cells.append(cell_match.group(2))

                # Match empty cell
                empty_cell_match = re.match(r'\s+- cell \[ref=\w+\]', cell_line)
                if empty_cell_match:
                    cells.append("")

                # Capture URL from tradesoft
                url_match = re.match(r'\s+- /url: (http://ar-demo\.tradesoft\.pro/.+)', cell_line)
                if url_match and cell_url is None:
                    cell_url = url_match.group(1).strip()

                j += 1

            # Parts have at least: position, image(empty), part_no, description, remark, quantity, model_data
            # cells[0] = position
            # cells[1] = empty (image placeholder)
            # cells[2] = part_no
            # cells[3] = description (may have extra text)
            # cells[4] = remark (may be empty)
            # cells[5] = quantity (ST)
            # cells[6] = model_data
            # cells[7] = "Add to Basket"

            if len(cells) >= 3 and cell_url:
                position_str = cells[0].strip()
                part_no = cells[2].strip() if len(cells) > 2 else ""

                if part_no and position_str.isdigit():
                    # Description: take only first line before "additionally"
                    raw_desc = cells[3].strip() if len(cells) > 3 else ""
                    # Strip "additionally to be used items: N" suffix
                    desc = re.sub(r'\s*additionally to be used items:.*$', '', raw_desc).strip()
                    # Also strip trailing " -"
                    desc = re.sub(r'\s*-\s*$', '', desc).strip()

                    remark = cells[4].strip() if len(cells) > 4 else ""
                    quantity_str = cells[5].strip() if len(cells) > 5 else ""
                    model_data = cells[6].strip() if len(cells) > 6 else ""

                    if part_no and desc:
                        item = {
                            "part_no": part_no,
                            "description": desc,
                            "url": cell_url,
                            "position": int(position_str),
                        }
                        if remark:
                            item["remark"] = remark
                        if quantity_str.isdigit():
                            item["quantity"] = int(quantity_str)
                        if model_data:
                            item["model_data"] = model_data
                        results.append(item)

            i = j
            continue

        return results

    def get_validator(self) -> type:
        return ParsedPart
