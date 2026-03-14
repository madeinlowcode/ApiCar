from fastapi import Header
from typing import Optional

from shared.database import get_db
from shared.config import settings
from app.exceptions import UnauthorizedException


async def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    if x_api_key is None or x_api_key != settings.ADMIN_API_KEY:
        raise UnauthorizedException("Invalid or missing API key")
    return x_api_key
