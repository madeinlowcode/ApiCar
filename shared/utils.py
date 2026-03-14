import re


def escape_like(value: str) -> str:
    """Escape LIKE metacharacters (%, _, \\) to prevent LIKE injection."""
    return re.sub(r"([%_\\])", r"\\\1", value)
