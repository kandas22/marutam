-- =====================================================
-- MIGRATION v3.0 — Align with ITBP RTC Grain Shop Spec
-- =====================================================
-- Run this migration against the existing schema to add:
-- 1. 'contractor' user role
-- 2. 'grain_shop' ration category (replacing 'grocery')
-- 3. Demands table and workflow
-- 4. Contractor supply tracking
-- 5. Price/unit change management
-- 6. Mess hierarchy (parent-child for sub-units)
-- 7. Contractor tender tracking
-- 8. Seed data for mess facilities

BEGIN;

-- =====================================================
-- 1. ADD 'contractor' TO user_role ENUM
-- =====================================================
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'contractor';

-- =====================================================
-- 2. ADD 'grain_shop' TO ration_category ENUM
-- =====================================================
-- Add 'grain_shop' category alongside existing 'grocery'
ALTER TYPE ration_category ADD VALUE IF NOT EXISTS 'grain_shop';

-- =====================================================
-- 3. ADD demand_status ENUM
-- =====================================================
CREATE TYPE demand_status AS ENUM (
    'draft',
    'submitted',
    'approved',
    'rejected',
    'forwarded_to_contractor',
    'supplied_to_controller',
    'distributed_to_messes'
);

-- =====================================================
-- 4. MODIFY CONTRACTORS TABLE — Add tender tracking
-- =====================================================
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS tender_year INTEGER;
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS tender_start_date DATE;
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS tender_end_date DATE;
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS notes TEXT;

CREATE INDEX IF NOT EXISTS idx_contractors_user ON contractors(user_id);
CREATE INDEX IF NOT EXISTS idx_contractors_tender ON contractors(tender_year);

-- =====================================================
-- 5. MODIFY ITEMS TABLE — Add price field
-- =====================================================
ALTER TABLE items ADD COLUMN IF NOT EXISTS price DECIMAL(10,2);
ALTER TABLE items ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);

-- =====================================================
-- 6. MODIFY MESS TABLE — Add parent_mess_id for sub-units
-- =====================================================
ALTER TABLE mess ADD COLUMN IF NOT EXISTS parent_mess_id UUID REFERENCES mess(id);
ALTER TABLE mess ADD COLUMN IF NOT EXISTS mess_type VARCHAR(50) DEFAULT 'primary';
-- mess_type: 'primary' or 'sub_unit'

CREATE INDEX IF NOT EXISTS idx_mess_parent ON mess(parent_mess_id);

-- =====================================================
-- 7. DEMANDS TABLE — Complete demand workflow
-- =====================================================
CREATE TABLE IF NOT EXISTS demands (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mess_id UUID REFERENCES mess(id) NOT NULL,
    demand_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status demand_status NOT NULL DEFAULT 'draft',
    notes TEXT,
    -- Submitted by mess member
    submitted_by UUID REFERENCES users(id),
    submitted_at TIMESTAMP WITH TIME ZONE,
    -- Consolidated by controller
    consolidated_by UUID REFERENCES users(id),
    consolidated_at TIMESTAMP WITH TIME ZONE,
    -- Approved/Rejected by admin
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    -- Forwarded to contractor
    forwarded_by UUID REFERENCES users(id),
    forwarded_at TIMESTAMP WITH TIME ZONE,
    -- Contractor reference
    contractor_id UUID REFERENCES contractors(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_demands_mess ON demands(mess_id);
CREATE INDEX IF NOT EXISTS idx_demands_status ON demands(status);
CREATE INDEX IF NOT EXISTS idx_demands_date ON demands(demand_date);
CREATE INDEX IF NOT EXISTS idx_demands_contractor ON demands(contractor_id);

-- =====================================================
-- 8. DEMAND ITEMS TABLE — Individual items in a demand
-- =====================================================
CREATE TABLE IF NOT EXISTS demand_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    demand_id UUID REFERENCES demands(id) ON DELETE CASCADE NOT NULL,
    item_id UUID REFERENCES items(id) NOT NULL,
    requested_quantity DECIMAL(10,2) NOT NULL,
    approved_quantity DECIMAL(10,2),
    unit VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_demand_items_demand ON demand_items(demand_id);
CREATE INDEX IF NOT EXISTS idx_demand_items_item ON demand_items(item_id);

-- =====================================================
-- 9. CONTRACTOR SUPPLIES TABLE — Supply tracking
-- =====================================================
CREATE TABLE IF NOT EXISTS contractor_supplies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    demand_id UUID REFERENCES demands(id),
    contractor_id UUID REFERENCES contractors(id) NOT NULL,
    item_id UUID REFERENCES items(id) NOT NULL,
    supplied_quantity DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(10,2),
    supply_date DATE NOT NULL DEFAULT CURRENT_DATE,
    received_by UUID REFERENCES users(id), -- Controller who received
    invoice_number VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_supplies_demand ON contractor_supplies(demand_id);
CREATE INDEX IF NOT EXISTS idx_supplies_contractor ON contractor_supplies(contractor_id);
CREATE INDEX IF NOT EXISTS idx_supplies_item ON contractor_supplies(item_id);
CREATE INDEX IF NOT EXISTS idx_supplies_date ON contractor_supplies(supply_date);

-- =====================================================
-- 10. PRICE CHANGE HISTORY TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS price_change_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id UUID REFERENCES items(id) NOT NULL,
    change_type VARCHAR(20) NOT NULL, -- 'price' or 'unit'
    old_value TEXT,
    new_value TEXT,
    proposed_by UUID REFERENCES users(id) NOT NULL,
    proposed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approval_status approval_status DEFAULT 'pending',
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_price_history_item ON price_change_history(item_id);
CREATE INDEX IF NOT EXISTS idx_price_history_status ON price_change_history(approval_status);

-- =====================================================
-- 11. TRIGGERS FOR NEW TABLES
-- =====================================================
CREATE TRIGGER update_demands_updated_at BEFORE UPDATE ON demands
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contractor_supplies_updated_at BEFORE UPDATE ON contractor_supplies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 12. VIEWS FOR NEW REPORTS
-- =====================================================

-- Demand Summary View
CREATE OR REPLACE VIEW demand_summary AS
SELECT 
    d.id as demand_id,
    d.demand_date,
    d.status,
    m.name as mess_name,
    u_sub.full_name as submitted_by_name,
    u_rev.full_name as reviewed_by_name,
    c.name as contractor_name,
    COUNT(di.id) as total_items,
    SUM(di.requested_quantity) as total_requested_quantity,
    SUM(di.approved_quantity) as total_approved_quantity,
    d.created_at,
    d.updated_at
FROM demands d
LEFT JOIN mess m ON d.mess_id = m.id
LEFT JOIN users u_sub ON d.submitted_by = u_sub.id
LEFT JOIN users u_rev ON d.reviewed_by = u_rev.id
LEFT JOIN contractors c ON d.contractor_id = c.id
LEFT JOIN demand_items di ON di.demand_id = d.id
GROUP BY d.id, d.demand_date, d.status, m.name, u_sub.full_name, u_rev.full_name, c.name, d.created_at, d.updated_at
ORDER BY d.demand_date DESC;

-- Contractor Supply Summary View
CREATE OR REPLACE VIEW contractor_supply_summary AS
SELECT 
    cs.supply_date,
    c.name as contractor_name,
    i.name as item_name,
    i.category,
    cs.supplied_quantity,
    cs.unit_price,
    (cs.supplied_quantity * COALESCE(cs.unit_price, 0)) as total_cost,
    i.unit,
    u.full_name as received_by_name
FROM contractor_supplies cs
JOIN contractors c ON cs.contractor_id = c.id
JOIN items i ON cs.item_id = i.id
LEFT JOIN users u ON cs.received_by = u.id
ORDER BY cs.supply_date DESC;

-- Financial Summary View
CREATE OR REPLACE VIEW financial_summary AS
SELECT 
    DATE_TRUNC('month', cs.supply_date) as month,
    i.category,
    SUM(cs.supplied_quantity * COALESCE(cs.unit_price, 0)) as total_expenditure,
    SUM(cs.supplied_quantity) as total_quantity,
    COUNT(DISTINCT cs.contractor_id) as contractors_involved
FROM contractor_supplies cs
JOIN items i ON cs.item_id = i.id
GROUP BY DATE_TRUNC('month', cs.supply_date), i.category
ORDER BY month DESC;

-- =====================================================
-- 13. ENABLE RLS ON NEW TABLES
-- =====================================================
ALTER TABLE demands ENABLE ROW LEVEL SECURITY;
ALTER TABLE demand_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractor_supplies ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_change_history ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- 14. SEED DATA — Mess Facilities
-- =====================================================

-- Insert primary mess facilities
INSERT INTO mess (name, location, capacity, mess_type) VALUES
    ('GO''s Mess', 'ITBP RTC', NULL, 'primary'),
    ('SO''s Mess', 'ITBP RTC', NULL, 'primary'),
    ('Adm Mess', 'ITBP RTC', NULL, 'primary'),
    ('Instructor Mess', 'ITBP RTC', NULL, 'primary'),
    ('Trainees Mess', 'ITBP RTC', NULL, 'primary')
ON CONFLICT DO NOTHING;

-- Insert Trainees Mess sub-units  
-- (We reference the parent by name since the ID is auto-generated)
DO $$
DECLARE
    trainees_mess_id UUID;
BEGIN
    SELECT id INTO trainees_mess_id FROM mess WHERE name = 'Trainees Mess' LIMIT 1;
    
    IF trainees_mess_id IS NOT NULL THEN
        INSERT INTO mess (name, location, capacity, mess_type, parent_mess_id) VALUES
            ('Karan Mess', 'ITBP RTC', NULL, 'sub_unit', trainees_mess_id),
            ('Abhimanyu Mess', 'ITBP RTC', NULL, 'sub_unit', trainees_mess_id),
            ('240 Men Mess', 'ITBP RTC', NULL, 'sub_unit', trainees_mess_id),
            ('Tent Area Mess', 'ITBP RTC', NULL, 'sub_unit', trainees_mess_id)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- =====================================================
-- 15. UPDATE EXISTING GROCERY ITEMS TO GRAIN_SHOP CATEGORY
-- =====================================================
-- Map 'grocery' items to 'grain_shop' for alignment with spec
-- (We keep both enum values for backward compatibility)
UPDATE items SET category = 'grain_shop' WHERE category = 'grocery';

COMMIT;
