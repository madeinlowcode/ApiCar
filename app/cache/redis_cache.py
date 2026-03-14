# Stub cache decorator - not implemented yet
import functools


def cached(ttl: int = 60, key_prefix: str = ""):
    """Stub cache decorator. Does nothing yet."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
