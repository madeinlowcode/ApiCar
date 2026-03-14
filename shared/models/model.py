from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Model(TimestampMixin, Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[int] = mapped_column(
        ForeignKey("markets.id", ondelete="CASCADE"), nullable=False
    )
    catalog_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    production_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    production_codes: Mapped[str | None] = mapped_column(String(200), nullable=True)
    catalog_url: Mapped[str] = mapped_column(Text, nullable=False)

    brand = relationship("Brand", back_populates="models")
    market = relationship("Market", back_populates="models")
    model_years = relationship("ModelYear", back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "brand_id", "market_id", "catalog_code", name="uq_model_brand_market_code"
        ),
    )
