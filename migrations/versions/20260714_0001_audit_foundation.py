"""Create the immutable MVP1 audit foundation.

Revision ID: 20260714_0001
Revises: None
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


audit_source_type = postgresql.ENUM(
    "pasted_text", name="audit_source_type", create_type=False
)
audit_language = postgresql.ENUM("en", "sk", name="audit_language", create_type=False)
audit_state = postgresql.ENUM(
    "queued",
    "running",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancel_requested",
    "cancelled",
    name="audit_state",
    create_type=False,
)
claim_type = postgresql.ENUM(
    "factual",
    "causal",
    "numerical",
    "comparative",
    "definitional",
    "recommendation",
    "other",
    name="claim_type",
    create_type=False,
)
claim_status = postgresql.ENUM(
    "low_risk",
    "review_recommended",
    "evidence_needed",
    "internally_inconsistent",
    "overstated",
    "not_verifiable",
    name="claim_status",
    create_type=False,
)
finding_source = postgresql.ENUM(
    "deterministic", "model_assisted", name="finding_source", create_type=False
)
finding_severity = postgresql.ENUM(
    "info",
    "low",
    "moderate",
    "high",
    "critical",
    name="finding_severity",
    create_type=False,
)
revision_validation_status = postgresql.ENUM(
    "pending",
    "valid",
    "invalid",
    name="revision_validation_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        audit_source_type,
        audit_language,
        audit_state,
        claim_type,
        claim_status,
        finding_source,
        finding_severity,
        revision_validation_status,
    ):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", audit_source_type, nullable=False),
        sa.Column("language", audit_language, nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("state", audit_state, nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("model_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("scoring_version", sa.String(length=64), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audits_created_at_desc", "audits", [sa.text("created_at DESC")])
    op.create_index("ix_audits_input_hash", "audits", ["input_hash"])
    op.create_index("ix_audits_state", "audits", ["state"])

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("primary_type", claim_type, nullable=True),
        sa.Column(
            "secondary_types",
            postgresql.ARRAY(sa.String(length=32)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("status", claim_status, nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("risk_score", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint("end_offset > start_offset", name="ck_claims_offset_order"),
        sa.CheckConstraint(
            "extraction_confidence BETWEEN 0 AND 1", name="ck_claims_confidence"
        ),
        sa.CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_claims_risk_score"),
        sa.CheckConstraint("start_offset >= 0", name="ck_claims_start_nonnegative"),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id", "ordinal", name="uq_claims_audit_ordinal"),
    )
    op.create_index("ix_claims_audit_status", "claims", ["audit_id", "status"])
    op.create_index(
        "ix_claims_audit_risk", "claims", ["audit_id", sa.text("risk_score DESC")]
    )

    op.create_table(
        "claim_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_type", sa.String(length=64), nullable=False),
        sa.Column("source_kind", finding_source, nullable=False),
        sa.Column("severity", finding_severity, nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_claim_findings_claim_type",
        "claim_findings",
        ["claim_id", "finding_type"],
    )

    op.create_table(
        "risk_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_type", sa.String(length=64), nullable=False),
        sa.Column("raw_value", postgresql.JSONB(), nullable=False),
        sa.Column("points", sa.SmallInteger(), nullable=False),
        sa.Column("explanation_message_key", sa.String(length=128), nullable=False),
        sa.Column("scoring_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint("points >= 0", name="ck_risk_components_points_nonnegative"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_components_claim", "risk_components", ["claim_id"])

    op.create_table(
        "suggested_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("replacement_text", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("language", audit_language, nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("validation_status", revision_validation_status, nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("redacted_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "audit_id", "sequence", name="uq_audit_events_audit_sequence"
        ),
    )

    op.execute(
        """
        CREATE FUNCTION protect_audit_immutability() RETURNS trigger AS $$
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

        CREATE TRIGGER audits_protect_immutability
        BEFORE UPDATE ON audits
        FOR EACH ROW EXECUTE FUNCTION protect_audit_immutability();

        CREATE FUNCTION protect_finalized_claim() RETURNS trigger AS $$
        DECLARE target_audit_id uuid;
        BEGIN
            target_audit_id := COALESCE(OLD.audit_id, NEW.audit_id);
            IF EXISTS (
                SELECT 1 FROM audits
                WHERE id = target_audit_id
                  AND state IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled')
            ) THEN
                RAISE EXCEPTION 'results of finalized audits are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER claims_protect_finalized
        BEFORE INSERT OR UPDATE ON claims
        FOR EACH ROW EXECUTE FUNCTION protect_finalized_claim();

        CREATE FUNCTION protect_finalized_claim_child() RETURNS trigger AS $$
        DECLARE target_claim_id uuid;
        BEGIN
            target_claim_id := COALESCE(OLD.claim_id, NEW.claim_id);
            IF EXISTS (
                SELECT 1 FROM claims c JOIN audits a ON a.id = c.audit_id
                WHERE c.id = target_claim_id
                  AND a.state IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled')
            ) THEN
                RAISE EXCEPTION 'results of finalized audits are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("claim_findings", "risk_components", "suggested_revisions"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_protect_finalized
            BEFORE INSERT OR UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION protect_finalized_claim_child();
            """
        )
    op.execute(
        """
        CREATE FUNCTION reject_audit_event_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_event_update();

        CREATE FUNCTION protect_finalized_audit_event() RETURNS trigger AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM audits
                WHERE id = NEW.audit_id
                  AND state IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled')
            ) THEN
                RAISE EXCEPTION 'results of finalized audits are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_events_protect_finalized
        BEFORE INSERT ON audit_events
        FOR EACH ROW EXECUTE FUNCTION protect_finalized_audit_event();
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS protect_finalized_audit_event() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_event_update() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS protect_finalized_claim_child() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS protect_finalized_claim() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS protect_audit_immutability() CASCADE")
    op.drop_table("audit_events")
    op.drop_table("suggested_revisions")
    op.drop_index("ix_risk_components_claim", table_name="risk_components")
    op.drop_table("risk_components")
    op.drop_index("ix_claim_findings_claim_type", table_name="claim_findings")
    op.drop_table("claim_findings")
    op.drop_index("ix_claims_audit_risk", table_name="claims")
    op.drop_index("ix_claims_audit_status", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_audits_state", table_name="audits")
    op.drop_index("ix_audits_input_hash", table_name="audits")
    op.drop_index("ix_audits_created_at_desc", table_name="audits")
    op.drop_table("audits")
    bind = op.get_bind()
    for enum in reversed(
        (
            audit_source_type,
            audit_language,
            audit_state,
            claim_type,
            claim_status,
            finding_source,
            finding_severity,
            revision_validation_status,
        )
    ):
        enum.drop(bind, checkfirst=True)
