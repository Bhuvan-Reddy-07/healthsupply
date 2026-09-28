-- Tamper-Evident Append-Only Enforcement for audit_log

CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'SECURITY VIOLATION: audit_log table is strictly append-only. UPDATE, DELETE, and TRUNCATE operations are forbidden by cryptographic and compliance constraints.';
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to table once created by Alembic/migration
-- (or in post-migration hook)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'audit_log') THEN
        DROP TRIGGER IF EXISTS trg_prevent_audit_log_update ON audit_log;
        CREATE TRIGGER trg_prevent_audit_log_update
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();

        -- Enforce at DB role level
        REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_log FROM PUBLIC;
    END IF;
END $$;
