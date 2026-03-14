from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class ModelYear(TimestampMixin, Base):
    __tablename__ = "model_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("models.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    restriction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    catalog_url: Mapped[str] = mapped_column(Text, nullable=False)

    model = relationship("Model", back_populates="model_years")
    parts_categories = relationship(
        "PartsCategory", back_populates="model_year", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_model_years_unique",
            "model_id",
            "year",
            text("COALESCE(restriction, '')"),
            unique=True,
        ),
    )
