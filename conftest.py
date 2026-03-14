"""Root conftest.py - sets UTF-8 mode for cross-platform file reading."""
import os

# Ensure UTF-8 is used for file I/O on Windows where default may be cp1252
os.environ.setdefault("PYTHONUTF8", "1")

# Also override the locale preferred encoding for open() calls
import io
import builtins

_original_open = builtins.open


def _utf8_open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
    """Override open() to default to UTF-8 encoding for text files."""
    if encoding is None and "b" not in str(mode):
        encoding = "utf-8"
    return _original_open(file, mode=mode, buffering=buffering, encoding=encoding,
                          errors=errors, newline=newline, closefd=closefd, opener=opener)


builtins.open = _utf8_open
