import re

from crawler.parsers.base import BaseParser
from crawler.validators.model import ParsedSubgroup


class SubgroupsParser(BaseParser):
    async def parse(self, page_content: str) -> list[dict]:
        """
        Parse the subgroups snapshot YAML to extract subgroup entries.

        The snapshot contains a table with rows like:
          row "MG Ill-No Description Remark Model data" [ref=eXX]:  <- header
          row "1 10003 base engine 1.0 ltr. petrol eng.+ CHZD" [ref=eXX]:
            - cell "1" [ref=eXX]
            - cell "10003" [ref=eXX]:
              - link "10003" [ref=eXX] [cursor=pointer]:
                - /url: http://catcar.info/...
            - cell "base engine" [ref=eXX]: base engine
            - cell "1.0 ltr." [ref=eXX]: 1.0 ltr.
            - cell "petrol eng.+ CHZD" [ref=eXX]:
        """
        results = []
        lines = page_content.split('\n')
        n = len(lines)

        i = 0
        while i < n:
            line = lines[i]

            row_match = re.match(r'(\s+)- row "(.+)" \[ref=\w+\]:', line)
            if row_match:
                row_indent = len(row_match.group(1))
                row_text = row_match.group(2)

                # Skip header row
                if 'MG' in row_text and 'Ill-No' in row_text and 'Description' in row_text:
                    i += 1
                    continue

                # Parse cells within this row
                cells = []
                cell_url = None
                cell_texts = {}  # index -> text content
                j = i + 1
                cell_idx = 0

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

                    # Match cell with content (and optional text after colon)
                    cell_match = re.match(r'\s+- cell "([^"]*)" \[ref=\w+\](: (.+))?', cell_line)
                    if cell_match:
                        cell_val = cell_match.group(1)
                        cells.append(cell_val)
                        cell_idx += 1

                    # Match empty cells
                    empty_cell_match = re.match(r'\s+- cell \[ref=\w+\]', cell_line)
                    if empty_cell_match:
                        cells.append("")
                        cell_idx += 1

                    # Capture URL from link inside Ill-No cell
                    url_match = re.match(r'\s+- /url: (http://catcar\.info/.+)', cell_line)
                    if url_match and cell_url is None:
                        cell_url = url_match.group(1).strip()

                    # Collect text lines for model_data (multi-line content)
                    text_match = re.match(r'\s+- text: (.+)', cell_line)
                    if text_match:
                        # This belongs to the last cell
                        pass

                    j += 1

                # cells[0] = MG (main group number)
                # cells[1] = Ill-No
                # cells[2] = description
                # cells[3] = remark
                # cells[4] = model_data (may be multi-line in YAML)
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
