from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class CrawlQueue(TimestampMixin, Base):
    __tablename__ = "crawl_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    retries: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    parent_brand_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("brands.id", ondelete="CASCADE"), nullable=True
    )
    parent_model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=True
    )
    parent_year_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("model_years.id", ondelete="CASCADE"), nullable=True
    )
    parent_category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("parts_categories.id", ondelete="CASCADE"), nullable=True
    )
    parent_subgroup_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("subgroups.id", ondelete="CASCADE"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("CrawlJob", back_populates="queue_items")

    __table_args__ = (
        # NOTE: num_nonnulls() is a PostgreSQL-specific function.
        # This constraint ensures at most one parent FK is set per row.
        # It will NOT be enforced on SQLite (used in tests); SQLite simply
        # ignores unknown functions inside CHECK constraints.
        CheckConstraint(
            "num_nonnulls(parent_brand_id, parent_model_id, parent_year_id, "
            "parent_category_id, parent_subgroup_id) <= 1",
            name="chk_single_parent",
        ),
        Index(
            "idx_crawl_queue_pending",
            "status",
            "level",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "idx_crawl_queue_failed",
            "status",
            postgresql_where=text("status = 'failed'"),
        ),
        Index("idx_crawl_queue_job", "job_id"),
    )
