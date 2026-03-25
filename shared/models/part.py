from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Part(TimestampMixin, Base):
    __tablename__ = "parts"
    __table_args__ = (
        Index(
            "idx_parts_unique",
            "subgroup_id",
            "part_number",
            text("COALESCE(position, '')"),
            unique=True,
        ),
        Index("idx_parts_part_number", "part_number"),
        Index("idx_parts_subgroup_id", "subgroup_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subgroup_id: Mapped[int] = mapped_column(
        ForeignKey("subgroups.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[str | None] = mapped_column(String(10), nullable=True)
    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quantity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    model_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # search_vector is a GENERATED ALWAYS tsvector column managed by PostgreSQL.
    # NOT in the model — Postgres computes it automatically on INSERT/UPDATE.

    subgroup = relationship("Subgroup", back_populates="parts")
