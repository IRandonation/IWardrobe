"""Store model-specific cutouts separately from original images."""

import sqlalchemy as sa
from alembic import op

revision = "7b9c2c42d1a0"
down_revision = "011ced53c92b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assets", sa.Column("display_model", sa.String(length=40), nullable=True))
    op.add_column("jobs", sa.Column("model", sa.String(length=40), nullable=True))
    op.add_column("jobs", sa.Column("output_key", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("model_version", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("jobs", "model_version")
    op.drop_column("jobs", "duration_ms")
    op.drop_column("jobs", "output_key")
    op.drop_column("jobs", "model")
    op.drop_column("assets", "display_model")
