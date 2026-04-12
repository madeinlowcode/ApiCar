"""HTML parser for L6 parts pages — used by the lightweight HTTP crawler."""
import re
from bs4 import BeautifulSoup


def parse_parts_html(html: str) -> list[dict]:
    """Parse parts from raw HTML of a catcar.info subgroup page.

    Each <tr name="POS"> contains:
      td[0] = position
      td[1] = part_number (with <a> link to tradesoft)
      td[2] = description (<b>title</b><br/>details)
      td[3] = remark (may be empty)
      td[4] = quantity
      td[5] = model_data
      td[6] = basket link (ignored)
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for tr in soup.select("tr[name]"):
        tds = tr.select("td.table__td")
        if len(tds) < 6:
            continue

        position = tds[0].get_text(strip=True)
        if not position.isdigit():
            continue

        # Part number from link
        link = tds[1].find("a")
        if not link:
            continue
        part_no = link.get_text(strip=True)
        url = link.get("href", "")

        if not part_no or not url:
            continue

        # Description: combine <b> bold title + remaining text
        desc_parts = []
        for child in tds[2].children:
            if child.name == "b":
                desc_parts.append(child.get_text(strip=True))
            elif child.name == "br":
                continue
            elif hasattr(child, "strip"):
                t = child.strip()
                if t:
                    desc_parts.append(t)
        description = " ".join(desc_parts).strip()
        # Strip trailing " -" and "additionally to be used items: N"
        description = re.sub(r"\s*additionally to be used items:.*$", "", description).strip()
        description = re.sub(r"\s*-\s*$", "", description).strip()

        if not description:
            continue

        remark = tds[3].get_text(strip=True)
        quantity = tds[4].get_text(strip=True)
        model_data = tds[5].get_text(strip=True) if len(tds) > 5 else ""

        item = {
            "part_no": part_no,
            "description": description,
            "url": url,
            "position": position,
        }
        if remark:
            item["remark"] = remark
        if quantity and quantity.isdigit():
            item["quantity"] = quantity
        if model_data and model_data not in ("----", "Add to Basket"):
            item["model_data"] = model_data

        results.append(item)

    return results
