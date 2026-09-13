"""001 initial schema

Revision ID: 001
Revises:
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Must exist before gen_random_uuid() server defaults are used
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("api_key_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "models",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("capabilities", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("context_window", sa.Integer, nullable=False),
        sa.Column("quality_score", sa.Float, nullable=False),
        sa.Column("input_price_per_1k", sa.Float, nullable=False),
        sa.Column("output_price_per_1k", sa.Float, nullable=False),
        sa.Column("avg_latency_ms", sa.Integer, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("prompt_meta", JSONB, nullable=True),
        sa.Column("strategy", sa.Text, nullable=False, server_default="balanced"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "routing_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", UUID(as_uuid=True), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("selected_model", sa.Text, sa.ForeignKey("models.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("candidates_json", JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
    )

    op.create_table(
        "model_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", UUID(as_uuid=True), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("model_id", sa.Text, sa.ForeignKey("models.id"), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="success"),
        sa.Column("fallback_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_runs")
    op.drop_table("routing_decisions")
    op.drop_table("requests")
    op.drop_table("models")
    op.drop_table("users")
