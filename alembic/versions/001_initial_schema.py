"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram similarity searches
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # brands
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("region", sa.String(20), nullable=False),
        sa.Column("catalog_path", sa.String(100), nullable=False),
        sa.Column("catalog_url", sa.Text(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "region IN ('Europe', 'Japan', 'Korea', 'USA')", name="chk_brand_region"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # markets
    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("catalog_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "name", name="uq_market_brand_name"),
    )

    # models
    op.create_table(
        "models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("catalog_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("production_date", sa.String(50), nullable=True),
        sa.Column("production_codes", sa.String(200), nullable=True),
        sa.Column("catalog_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brand_id", "market_id", "catalog_code", name="uq_model_brand_market_code"
        ),
    )

    # model_years
    op.create_table(
        "model_years",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("restriction", sa.String(200), nullable=True),
        sa.Column("catalog_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_model_years_unique",
        "model_years",
        ["model_id", "year", sa.text("COALESCE(restriction, '')")],
        unique=True,
    )

    # parts_categories
    op.create_table(
        "parts_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_year_id", sa.Integer(), nullable=False),
        sa.Column("category_index", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("catalog_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_year_id"], ["model_years.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_year_id", "category_index", name="uq_category_year_index"),
    )

    # subgroups
    op.create_table(
        "subgroups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("main_group", sa.String(10), nullable=False),
        sa.Column("illustration_number", sa.String(20), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("remark", sa.String(300), nullable=True),
        sa.Column("model_data", sa.Text(), nullable=True),
        sa.Column("catalog_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["parts_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_id", "illustration_number", name="uq_subgroup_category_illustration"
        ),
    )

    # parts
    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subgroup_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(10), nullable=True),
        sa.Column("part_number", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("remark", sa.String(300), nullable=True),
        sa.Column("quantity", sa.String(10), nullable=True),
        sa.Column("model_data", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["subgroup_id"], ["subgroups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_parts_unique",
        "parts",
        ["subgroup_id", "part_number", sa.text("COALESCE(position, '')")],
        unique=True,
    )
    op.create_index("idx_parts_part_number", "parts", ["part_number"])
    op.create_index("idx_parts_subgroup_id", "parts", ["subgroup_id"])

    # PostgreSQL-specific: pg_trgm GIN index on part_number
    op.execute(
        "CREATE INDEX idx_parts_part_number_trgm ON parts USING GIN (part_number gin_trgm_ops)"
    )

    # PostgreSQL-specific: search_vector generated column + GIN index
    op.execute(
        """
        ALTER TABLE parts ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', COALESCE(description, '') || ' ' || COALESCE(part_number, ''))
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX idx_parts_search_vector ON parts USING GIN (search_vector)"
    )

    # crawl_jobs
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # crawl_queue
    op.create_table(
        "crawl_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("retries", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("parent_brand_id", sa.Integer(), nullable=True),
        sa.Column("parent_model_id", sa.Integer(), nullable=True),
        sa.Column("parent_year_id", sa.Integer(), nullable=True),
        sa.Column("parent_category_id", sa.Integer(), nullable=True),
        sa.Column("parent_subgroup_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "num_nonnulls(parent_brand_id, parent_model_id, parent_year_id, "
            "parent_category_id, parent_subgroup_id) <= 1",
            name="chk_single_parent",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["parent_model_id"], ["models.id"]),
        sa.ForeignKeyConstraint(["parent_year_id"], ["model_years.id"]),
        sa.ForeignKeyConstraint(["parent_category_id"], ["parts_categories.id"]),
        sa.ForeignKeyConstraint(["parent_subgroup_id"], ["subgroups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_crawl_queue_job", "crawl_queue", ["job_id"])
    # Partial indexes (PostgreSQL-specific)
    op.execute(
        "CREATE INDEX idx_crawl_queue_pending ON crawl_queue (status, level) "
        "WHERE status = 'pending'"
    )
    op.execute(
        "CREATE INDEX idx_crawl_queue_failed ON crawl_queue (status) "
        "WHERE status = 'failed'"
    )


def downgrade() -> None:
    op.drop_table("crawl_queue")
    op.drop_table("crawl_jobs")
    op.drop_index("idx_parts_search_vector", table_name="parts")
    op.drop_index("idx_parts_part_number_trgm", table_name="parts")
    op.drop_index("idx_parts_subgroup_id", table_name="parts")
    op.drop_index("idx_parts_part_number", table_name="parts")
    op.drop_index("idx_parts_unique", table_name="parts")
    op.drop_table("parts")
    op.drop_table("subgroups")
    op.drop_table("parts_categories")
    op.drop_index("idx_model_years_unique", table_name="model_years")
    op.drop_table("model_years")
    op.drop_table("models")
    op.drop_table("markets")
    op.drop_table("brands")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
