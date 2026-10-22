"""Weather recommendation tags, preferences and saved outfit runs."""

import sqlalchemy as sa
from alembic import op

revision = "4f6e8d9a2b10"
down_revision = "7b9c2c42d1a0"
branch_labels = None
depends_on = None

TAGS = (
    "warmth",
    "layer",
    "sleeve_length",
    "bottom_length",
    "style",
    "rain_protection",
    "wind_protection",
)


def upgrade():
    for tag in TAGS:
        op.add_column(
            "garments", sa.Column(tag, sa.String(20), nullable=False, server_default="unknown")
        )
    op.create_table(
        "recommendation_preferences",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_runs_user_id", "recommendation_runs", ["user_id"])


def downgrade():
    op.drop_table("recommendation_runs")
    op.drop_table("recommendation_preferences")
    for tag in reversed(TAGS):
        op.drop_column("garments", tag)
