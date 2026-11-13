-- Apply once to an existing PostgreSQL database before deploying this code.
-- Valid legacy JSON keeps its JSON structure. Invalid legacy text is preserved as a
-- JSON string; these old rows are marked "legacy" and cannot be cache hits.
BEGIN;

DO $$
DECLARE
    legacy_row RECORD;
BEGIN
    FOR legacy_row IN
        SELECT id, analysis
        FROM public.github_analysis
    LOOP
        BEGIN
            PERFORM legacy_row.analysis::jsonb;
        EXCEPTION WHEN invalid_text_representation THEN
            UPDATE public.github_analysis
            SET analysis = to_json(legacy_row.analysis)::text
            WHERE id = legacy_row.id;
        END;
    END LOOP;
END
$$;

ALTER TABLE github_analysis
    ALTER COLUMN analysis TYPE JSONB USING analysis::jsonb;

ALTER TABLE github_analysis
    ADD COLUMN IF NOT EXISTS analysis_version VARCHAR(64) NOT NULL DEFAULT 'legacy';

CREATE INDEX IF NOT EXISTS ix_github_analysis_analysis_version
    ON github_analysis (analysis_version);

COMMIT;
