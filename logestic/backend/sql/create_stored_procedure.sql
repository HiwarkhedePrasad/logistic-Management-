-- Script to create all used PostgreSQL functions (replaces stored procedures)

-- Enhanced function that returns all data needed for various risk agents
CREATE OR REPLACE FUNCTION get_schedule_comparison_data()
RETURNS TABLE (
    project_id INT,
    project_name VARCHAR(100),
    project_code VARCHAR(20),
    project_country VARCHAR(100),
    project_location VARCHAR(255),
    equipment_id INT,
    equipment_code VARCHAR(20),
    equipment_name VARCHAR(100),
    equipment_type VARCHAR(50),
    work_package_id INT,
    work_package_code VARCHAR(20),
    work_package_name VARCHAR(100),
    milestone_id INT,
    milestone_number VARCHAR(20),
    milestone_activity VARCHAR(100),
    p6_schedule_due_date DATE,
    equipment_milestone_due_date DATE,
    days_variance INT,
    days_until_p6_due INT,
    supplier_id INT,
    supplier_name VARCHAR(100),
    supplier_number VARCHAR(20),
    purchase_order_id INT,
    purchase_order_number VARCHAR(50),
    line_item VARCHAR(20),
    amount DECIMAL(18,2),
    supplier_lead_time INT,
    manufacturing_location VARCHAR(255),
    shipping_port VARCHAR(100),
    receiving_port VARCHAR(100),
    logistics_method VARCHAR(50),
    alternative_suppliers TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        -- Basic project and equipment info
        p.project_id,
        p.project_name,
        p.project_code,
        p.project_country,
        p.project_location,
        eq.equipment_id,
        eq.equipment_code,
        eq.equipment_name,
        eq.equipment_type,
        wp.work_package_id,
        wp.work_package_code,
        wp.work_package_name,
        m.milestone_id,
        m.milestone_number,
        m.milestone_activity,
        
        -- Schedule dates
        ps.p6_schedule_due_date,
        ems.equipment_milestone_due_date,
        (ems.equipment_milestone_due_date - ps.p6_schedule_due_date)::INT AS days_variance,
        (ps.p6_schedule_due_date - CURRENT_DATE)::INT AS days_until_p6_due,
        
        -- Supplier info
        s.supplier_id,
        s.supplier_name,
        s.supplier_number,
        po.purchase_order_id,
        po.purchase_order_number,
        po.line_item,
        po.amount,
        es.lead_time_days AS supplier_lead_time,
        
        -- Manufacturing location data (for Political & Tariff risk)
        ml.location_address AS manufacturing_location,
        
        -- Logistics data (for Logistics risk)
        li.shipping_port,
        li.receiving_port,
        li.logistics_method,
        
        -- Alternative suppliers
        (
            SELECT string_agg(
                alt_s.supplier_name || ' (Cost: ' || 
                es2.unit_cost::TEXT || ', Lead time: ' || 
                es2.lead_time_days::TEXT || ' days)', ', '
            )
            FROM dim_equipment_supplier es2
            JOIN dim_supplier alt_s ON es2.supplier_id = alt_s.supplier_id
            WHERE es2.equipment_id = eq.equipment_id AND es2.supplier_id != s.supplier_id
        ) AS alternative_suppliers
        
    FROM fact_p6_schedule ps
    JOIN fact_equipment_milestone_schedule ems ON 
        ps.equipment_id = ems.equipment_id AND 
        ps.milestone_id = ems.milestone_id AND
        ps.project_id = ems.project_id AND
        ps.work_package_id = ems.work_package_id
    JOIN dim_project p ON ps.project_id = p.project_id
    JOIN dim_equipment eq ON ps.equipment_id = eq.equipment_id
    JOIN dim_work_package wp ON ps.work_package_id = wp.work_package_id
    JOIN dim_milestone m ON ps.milestone_id = m.milestone_id
    JOIN fact_purchase_order po ON ems.purchase_order_id = po.purchase_order_id
    JOIN dim_supplier s ON po.supplier_id = s.supplier_id
    
    -- Join equipment supplier to get lead time
    LEFT JOIN dim_equipment_supplier es ON 
        es.equipment_id = eq.equipment_id AND 
        es.supplier_id = s.supplier_id
    
    -- Join manufacturing location
    LEFT JOIN dim_manufacturing_location ml ON 
        ml.equipment_id = eq.equipment_id AND 
        ml.supplier_id = s.supplier_id
    
    -- Join logistics info
    LEFT JOIN dim_logistics_info li ON 
        li.equipment_id = eq.equipment_id AND 
        li.supplier_id = s.supplier_id
    
    WHERE 
        m.milestone_id = 7; -- Delivery to Site milestone
END;
$$ LANGUAGE plpgsql;


-- Function for getting recent conversations
CREATE OR REPLACE FUNCTION get_recent_conversations(row_limit INT DEFAULT 10)
RETURNS TABLE (
    session_id VARCHAR(100),
    conversation_id UUID,
    first_query TEXT,
    last_event_time TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (e.conversation_id)
        e.session_id,
        e.conversation_id,
        e.user_query AS first_query,
        e.event_time AS last_event_time
    FROM dim_agent_event_log e
    WHERE e.user_query IS NOT NULL
    ORDER BY e.conversation_id, e.event_time DESC
    LIMIT row_limit;
END;
$$ LANGUAGE plpgsql;