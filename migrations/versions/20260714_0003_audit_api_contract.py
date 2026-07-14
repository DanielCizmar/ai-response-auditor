"""Add audit request identity, re-audit lineage, and claim review semantics.

Revision ID: 20260714_0003
Revises: 20260714_0002
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0003"
down_revision: str | None = "20260714_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    atomicity = postgresql.ENUM("atomic", "compound", name="claim_atomicity")
    verifiability = postgresql.ENUM(
        "externally_verifiable",
        "internally_verifiable",
        "not_verifiable",
        name="claim_verifiability",
    )
    atomicity.create(op.get_bind(), checkfirst=True)
    verifiability.create(op.get_bind(), checkfirst=True)

    op.add_column("audits", sa.Column("idempotency_key", sa.String(128)))
    op.execute("UPDATE audits SET idempotency_key = id::text")
    op.alter_column("audits", "idempotency_key", nullable=False)
    op.create_unique_constraint(
        "uq_audits_idempotency_key", "audits", ["idempotency_key"]
    )
    op.add_column(
        "audits",
        sa.Column(
            "re_audit_of_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="RESTRICT"),
        ),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_audit_immutability() RETURNS trigger AS $$
        BEGIN
            IF ROW(NEW.id, NEW.idempotency_key, NEW.re_audit_of_id,
                   NEW.source_type, NEW.language, NEW.input_text,
                   NEW.input_hash, NEW.pipeline_version, NEW.model_manifest,
                   NEW.scoring_version, NEW.normalization_version)
               IS DISTINCT FROM
               ROW(OLD.id, OLD.idempotency_key, OLD.re_audit_of_id,
                   OLD.source_type, OLD.language, OLD.input_text,
                   OLD.input_hash, OLD.pipeline_version, OLD.model_manifest,
                   OLD.scoring_version, OLD.normalization_version) THEN
                RAISE EXCEPTION 'audit input and version identity are immutable';
            END IF;
            IF OLD.state IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled') THEN
                RAISE EXCEPTION 'finalized audits are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.add_column(
        "claims",
        sa.Column(
            "atomicity",
            atomicity,
            nullable=False,
            server_default="atomic",
        ),
    )
    op.add_column(
        "claims",
        sa.Column(
            "verifiability",
            verifiability,
            nullable=False,
            server_default="externally_verifiable",
        ),
    )
    op.alter_column("claims", "atomicity", server_default=None)
    op.alter_column("claims", "verifiability", server_default=None)


def downgrade() -> None:
    op.drop_column("claims", "verifiability")
    op.drop_column("claims", "atomicity")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_audit_immutability() RETURNS trigger AS $$
        BEGIN
            IF ROW(NEW.id, NEW.source_type, NEW.language, NEW.input_text,
                   NEW.input_hash, NEW.pipeline_version, NEW.model_manifest,
                   NEW.scoring_version, NEW.normalization_version)
               IS DISTINCT FROM
               ROW(OLD.id, OLD.source_type, OLD.language, OLD.input_text,
                   OLD.input_hash, OLD.pipeline_version, OLD.model_manifest,
                   OLD.scoring_version, OLD.normalization_version) THEN
                RAISE EXCEPTION 'audit input and version identity are immutable';
            END IF;
            IF OLD.state IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled') THEN
                RAISE EXCEPTION 'finalized audits are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.drop_column("audits", "re_audit_of_id")
    op.drop_constraint("uq_audits_idempotency_key", "audits", type_="unique")
    op.drop_column("audits", "idempotency_key")
    postgresql.ENUM(name="claim_verifiability").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="claim_atomicity").drop(op.get_bind(), checkfirst=True)
