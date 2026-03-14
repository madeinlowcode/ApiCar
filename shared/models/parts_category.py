from sqlalchemy import ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class PartsCategory(TimestampMixin, Base):
    __tablename__ = "parts_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_year_id: Mapped[int] = mapped_column(
        ForeignKey("model_years.id", ondelete="CASCADE"), nullable=False
    )
    category_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    catalog_url: Mapped[str] = mapped_column(Text, nullable=False)

    model_year = relationship("ModelYear", back_populates="parts_categories")
    subgroups = relationship("Subgroup", back_populates="category", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("model_year_id", "category_index", name="uq_category_year_index"),
    )
