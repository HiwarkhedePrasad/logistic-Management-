-- PostgreSQL script to drop all tables (replaces MS SQL stored procedure)

CREATE OR REPLACE FUNCTION drop_all_project_tables()
RETURNS VOID AS $$
BEGIN
    -- Drop fact tables first (they have foreign keys)
    DROP TABLE IF EXISTS fact_risk_report CASCADE;
    DROP TABLE IF EXISTS fact_equipment_milestone_schedule CASCADE;
    DROP TABLE IF EXISTS fact_p6_schedule CASCADE;
    DROP TABLE IF EXISTS fact_purchase_order CASCADE;
    
    -- Drop junction/link tables
    DROP TABLE IF EXISTS dim_equipment_supplier CASCADE;
    DROP TABLE IF EXISTS dim_manufacturing_location CASCADE;
    DROP TABLE IF EXISTS dim_logistics_info CASCADE;
    
    -- Drop agent/logging tables
    DROP TABLE IF EXISTS dim_agent_event_log CASCADE;
    DROP TABLE IF EXISTS dim_agent_thinking_log CASCADE;
    
    -- Drop dimension tables
    DROP TABLE IF EXISTS dim_milestone CASCADE;
    DROP TABLE IF EXISTS dim_equipment CASCADE;
    DROP TABLE IF EXISTS dim_work_package CASCADE;
    DROP TABLE IF EXISTS dim_supplier CASCADE;
    DROP TABLE IF EXISTS dim_project CASCADE;
    
    RAISE NOTICE 'All project tables dropped successfully';
END;
$$ LANGUAGE plpgsql;

-- To execute: SELECT drop_all_project_tables();