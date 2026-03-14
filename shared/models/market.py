from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Market(TimestampMixin, Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    catalog_url: Mapped[str] = mapped_column(Text, nullable=False)

    brand = relationship("Brand", back_populates="markets")
    models = relationship("Model", back_populates="market", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("brand_id", "name", name="uq_market_brand_name"),
    )
