from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Brand(TimestampMixin, Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    catalog_path: Mapped[str] = mapped_column(String(100), nullable=False)
    catalog_url: Mapped[str] = mapped_column(Text, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    markets = relationship("Market", back_populates="brand", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="brand", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJob", back_populates="brand", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "region IN ('Europe', 'Japan', 'Korea', 'USA')", name="chk_brand_region"
        ),
    )
