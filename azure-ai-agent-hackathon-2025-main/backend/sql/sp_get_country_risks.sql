-- PostgreSQL function for Country Risk Heatmap Data
-- Replaces the MS SQL stored procedure [dbo].[GetCountryRiskHeatmapData]

CREATE OR REPLACE FUNCTION get_country_risk_heatmap_data(
    p_conversation_id TEXT DEFAULT NULL,
    p_session_id TEXT DEFAULT NULL
)
RETURNS TABLE (
    datetime_stamp TEXT,
    conversation_id TEXT,
    session_id TEXT,
    country TEXT,
    average_risk NUMERIC,
    breakdown JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH political_risks AS (
        -- Extract political risks from agent event log JSON output
        SELECT
            dat.conversation_id::TEXT AS conv_id,
            dat.session_id AS sess_id,
            TRIM(country_split.country_name) AS country_name,
            pr->>'political_type' AS political_type,
            pr->>'risk_information' AS risk_information,
            COALESCE((pr->>'likelihood')::INT, 0) AS likelihood,
            pr->>'likelihood_reasoning' AS likelihood_reasoning,
            pr->>'publication_date' AS publication_date,
            pr->>'citation_title' AS citation_title,
            pr->>'citation_name' AS citation_name,
            pr->>'citation_url' AS citation_url
        FROM dim_agent_event_log AS dat,
            jsonb_array_elements((dat.agent_output::jsonb)->'political_risks') AS pr,
            regexp_split_to_table(pr->>'country', '-') AS country_split(country_name)
        WHERE dat.action = 'Political Risk JSON Data'
            AND (dat.agent_output::jsonb)->'political_risks' IS NOT NULL
            AND jsonb_array_length((dat.agent_output::jsonb)->'political_risks') > 0
            AND (p_conversation_id IS NULL OR dat.conversation_id::TEXT = p_conversation_id)
            AND (p_session_id IS NULL OR dat.session_id = p_session_id)
    ),
    country_summary AS (
        SELECT
            conv_id,
            sess_id,
            country_name,
            SUM(likelihood::NUMERIC) AS total_likelihood,
            COUNT(*) AS risk_count
        FROM political_risks
        GROUP BY conv_id, sess_id, country_name
    ),
    country_data AS (
        SELECT
            cs.conv_id,
            cs.sess_id,
            cs.country_name,
            ROUND(cs.total_likelihood / NULLIF(cs.risk_count, 0), 0) AS avg_risk,
            (
                SELECT jsonb_agg(jsonb_build_object(
                    'country', pr.country_name,
                    'description', pr.political_type,
                    'summary', pr.risk_information,
                    'likelihood', pr.likelihood,
                    'likelihood_reasoning', pr.likelihood_reasoning,
                    'publication_date', pr.publication_date,
                    'source', pr.citation_name,
                    'source_url', pr.citation_url
                ))
                FROM political_risks pr
                WHERE pr.country_name = cs.country_name
                  AND pr.conv_id = cs.conv_id
                  AND pr.sess_id = cs.sess_id
            ) AS breakdown_json
        FROM country_summary cs
    )
    SELECT
        TO_CHAR(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS') AS datetime_stamp,
        cd.conv_id AS conversation_id,
        cd.sess_id AS session_id,
        cd.country_name AS country,
        cd.avg_risk AS average_risk,
        cd.breakdown_json AS breakdown
    FROM country_data cd;
END;
$$ LANGUAGE plpgsql;
