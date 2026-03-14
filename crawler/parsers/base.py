from abc import ABC, abstractmethod

from pydantic import BaseModel


class BaseParser(ABC):
    @abstractmethod
    async def parse(self, page_content: str) -> list[dict]:
        """Parse page content and return list of extracted data."""
        raise NotImplementedError

    @abstractmethod
    def get_validator(self) -> type[BaseModel]:
        """Return the Pydantic validator for this parser's output."""
        raise NotImplementedError
