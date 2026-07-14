"""Reject claims whose offsets do not map to immutable audit text.

Revision ID: 20260714_0002
Revises: 20260714_0001
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260714_0002"
down_revision: str | None = "20260714_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_claim_source_span() RETURNS trigger AS $$
        DECLARE source_text text;
        BEGIN
            SELECT input_text INTO source_text FROM audits WHERE id = NEW.audit_id;
            IF source_text IS NULL THEN
                RAISE EXCEPTION 'claim audit does not exist';
            END IF;
            IF NEW.start_offset < 0
               OR NEW.end_offset <= NEW.start_offset
               OR NEW.end_offset > char_length(source_text)
               OR substring(
                    source_text
                    FROM NEW.start_offset + 1
                    FOR NEW.end_offset - NEW.start_offset
                  ) IS DISTINCT FROM NEW.exact_text THEN
                RAISE EXCEPTION 'claim offsets do not match immutable audit input';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER claims_validate_source_span
        BEFORE INSERT OR UPDATE OF audit_id, start_offset, end_offset, exact_text
        ON claims
        FOR EACH ROW EXECUTE FUNCTION validate_claim_source_span();
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS validate_claim_source_span() CASCADE")
