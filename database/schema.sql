-- ITBP RTC Grain Shop Management System
-- Database Schema for Supabase PostgreSQL

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- ENUM TYPES
-- =====================================================

-- User roles enum
CREATE TYPE user_role AS ENUM ('admin', 'mess_user', 'grain_shop_user');

-- Ration categories enum
CREATE TYPE ration_category AS ENUM ('veg', 'non_veg', 'grocery');

-- Approval status enum
CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected');

-- Transaction type enum
CREATE TYPE transaction_type AS ENUM ('incoming', 'outgoing');

-- =====================================================
-- TABLES
-- =====================================================

-- Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'mess_user',
    phone VARCHAR(20) NOT NULL,
    manager_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_manager ON users(manager_id);

-- Contractors Table
CREATE TABLE contractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    gst_number VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contractors_name ON contractors(name);

-- Mess Table (Different mess units)
CREATE TABLE mess (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    capacity INTEGER,
    manager_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mess_manager ON mess(manager_id);

-- Items Master Table (All ration items)
CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category ration_category NOT NULL,
    unit VARCHAR(50) NOT NULL, -- kg, liters, pieces, etc.
    description TEXT,
    minimum_stock DECIMAL(10,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_items_category ON items(category);
CREATE INDEX idx_items_name ON items(name);

-- Grain Shop Inventory (Contractor supplied items to grain shop)
CREATE TABLE grain_shop_inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id UUID REFERENCES items(id) NOT NULL,
    contractor_id UUID REFERENCES contractors(id) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(10,2),
    batch_number VARCHAR(100),
    received_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date DATE,
    recorded_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_grain_inventory_item ON grain_shop_inventory(item_id);
CREATE INDEX idx_grain_inventory_contractor ON grain_shop_inventory(contractor_id);
CREATE INDEX idx_grain_inventory_date ON grain_shop_inventory(received_date);

-- Mess Inventory (Items distributed to mess)
CREATE TABLE mess_inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mess_id UUID REFERENCES mess(id) NOT NULL,
    item_id UUID REFERENCES items(id) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    recorded_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mess_inventory_mess ON mess_inventory(mess_id);
CREATE INDEX idx_mess_inventory_item ON mess_inventory(item_id);
CREATE INDEX idx_mess_inventory_date ON mess_inventory(date);

-- Daily Ration Usage (Mess daily consumption)
CREATE TABLE daily_ration_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mess_id UUID REFERENCES mess(id) NOT NULL,
    item_id UUID REFERENCES items(id) NOT NULL,
    quantity_used DECIMAL(10,2) NOT NULL,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    meal_type VARCHAR(50), -- breakfast, lunch, dinner
    personnel_count INTEGER,
    notes TEXT,
    recorded_by UUID REFERENCES users(id),
    approval_status approval_status DEFAULT 'pending',
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_daily_usage_mess ON daily_ration_usage(mess_id);
CREATE INDEX idx_daily_usage_date ON daily_ration_usage(usage_date);
CREATE INDEX idx_daily_usage_status ON daily_ration_usage(approval_status);

-- Pending Updates Table (For approval workflow)
CREATE TABLE pending_updates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    requested_by UUID REFERENCES users(id) NOT NULL,
    approval_status approval_status DEFAULT 'pending',
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pending_updates_status ON pending_updates(approval_status);
CREATE INDEX idx_pending_updates_table ON pending_updates(table_name);
CREATE INDEX idx_pending_updates_requester ON pending_updates(requested_by);

-- Distribution Log (Grain shop to Mess distribution)
CREATE TABLE distribution_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grain_shop_inventory_id UUID REFERENCES grain_shop_inventory(id),
    mess_id UUID REFERENCES mess(id) NOT NULL,
    item_id UUID REFERENCES items(id) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    distribution_date DATE NOT NULL DEFAULT CURRENT_DATE,
    distributed_by UUID REFERENCES users(id),
    received_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_distribution_mess ON distribution_log(mess_id);
CREATE INDEX idx_distribution_date ON distribution_log(distribution_date);

-- Activity Log (For tracking data flow)
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(50) NOT NULL, -- CREATE, UPDATE, DELETE, LOGIN, LOGOUT
    table_name VARCHAR(100),
    record_id UUID,
    old_data JSONB,
    new_data JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_log_user ON activity_log(user_id);
CREATE INDEX idx_activity_log_action ON activity_log(action);
CREATE INDEX idx_activity_log_date ON activity_log(created_at);
CREATE INDEX idx_activity_log_table ON activity_log(table_name);

-- =====================================================
-- VIEWS FOR REPORTING
-- =====================================================

-- Daily Data Flow Summary View
CREATE OR REPLACE VIEW daily_data_flow_summary AS
SELECT 
    DATE(al.created_at) as activity_date,
    al.table_name,
    al.action,
    u.role as user_role,
    COUNT(*) as action_count
FROM activity_log al
LEFT JOIN users u ON al.user_id = u.id
GROUP BY DATE(al.created_at), al.table_name, al.action, u.role
ORDER BY DATE(al.created_at) DESC;

-- Grain Shop Daily Summary View
CREATE OR REPLACE VIEW grain_shop_daily_summary AS
SELECT 
    gsi.received_date,
    c.name as contractor_name,
    i.name as item_name,
    i.category,
    SUM(gsi.quantity) as total_quantity,
    i.unit
FROM grain_shop_inventory gsi
JOIN contractors c ON gsi.contractor_id = c.id
JOIN items i ON gsi.item_id = i.id
GROUP BY gsi.received_date, c.name, i.name, i.category, i.unit
ORDER BY gsi.received_date DESC;

-- Mess Daily Consumption Summary View
CREATE OR REPLACE VIEW mess_daily_summary AS
SELECT 
    dru.usage_date,
    m.name as mess_name,
    i.name as item_name,
    i.category,
    SUM(dru.quantity_used) as total_used,
    i.unit,
    dru.approval_status
FROM daily_ration_usage dru
JOIN mess m ON dru.mess_id = m.id
JOIN items i ON dru.item_id = i.id
GROUP BY dru.usage_date, m.name, i.name, i.category, i.unit, dru.approval_status
ORDER BY dru.usage_date DESC;

-- =====================================================
-- FUNCTIONS & TRIGGERS
-- =====================================================

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers to all tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contractors_updated_at BEFORE UPDATE ON contractors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_mess_updated_at BEFORE UPDATE ON mess
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_items_updated_at BEFORE UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_grain_shop_inventory_updated_at BEFORE UPDATE ON grain_shop_inventory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_mess_inventory_updated_at BEFORE UPDATE ON mess_inventory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_ration_usage_updated_at BEFORE UPDATE ON daily_ration_usage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractors ENABLE ROW LEVEL SECURITY;
ALTER TABLE mess ENABLE ROW LEVEL SECURITY;
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE grain_shop_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE mess_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_ration_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE pending_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE distribution_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- SEED DATA
-- =====================================================

-- Insert default admin user (password: admin123)
-- Password hash for 'admin123' using bcrypt
INSERT INTO users (username, email, password_hash, full_name, role, phone, is_active)
VALUES (
    'admin',
    'admin@itbp.gov.in',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.7NHzZKE5sKJHYW',
    'ITBP Admin',
    'admin',
    '0000000000',
    TRUE
);

-- Insert sample items
INSERT INTO items (name, category, unit, minimum_stock) VALUES
-- Vegetables
('Rice', 'veg', 'kg', 100),
('Wheat Flour', 'veg', 'kg', 50),
('Dal (Toor)', 'veg', 'kg', 25),
('Dal (Moong)', 'veg', 'kg', 25),
('Potatoes', 'veg', 'kg', 50),
('Onions', 'veg', 'kg', 30),
('Tomatoes', 'veg', 'kg', 20),
('Green Vegetables', 'veg', 'kg', 40),
-- Non-Veg
('Chicken', 'non_veg', 'kg', 30),
('Mutton', 'non_veg', 'kg', 20),
('Fish', 'non_veg', 'kg', 15),
('Eggs', 'non_veg', 'pieces', 500),
-- Grocery
('Cooking Oil', 'grocery', 'liters', 50),
('Sugar', 'grocery', 'kg', 30),
('Salt', 'grocery', 'kg', 20),
('Tea', 'grocery', 'kg', 10),
('Milk Powder', 'grocery', 'kg', 15),
('Spices Mix', 'grocery', 'kg', 5);

COMMIT;
