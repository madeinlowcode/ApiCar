from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Subgroup(TimestampMixin, Base):
    __tablename__ = "subgroups"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("parts_categories.id", ondelete="CASCADE"), nullable=False
    )
    main_group: Mapped[str] = mapped_column(String(50), nullable=False)
    illustration_number: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String(600), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(300), nullable=True)
    model_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalog_url: Mapped[str] = mapped_column(Text, nullable=False)

    category = relationship("PartsCategory", back_populates="subgroups")
    parts = relationship("Part", back_populates="subgroup", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "category_id", "illustration_number", name="uq_subgroup_category_illustration"
        ),
    )
