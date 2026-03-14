from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Part(TimestampMixin, Base):
    __tablename__ = "parts"

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
    # On PostgreSQL this column is overridden by the migration with a
    # tsvector GENERATED ALWAYS AS (STORED) expression.  On SQLite (tests)
    # it is simply a nullable TEXT column that is never populated.
    search_vector: Mapped[str | None] = mapped_column(Text, nullable=True, insert_default=None)

    subgroup = relationship("Subgroup", back_populates="parts")

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
