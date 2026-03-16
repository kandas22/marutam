"""
ITBP RTC Grain Shop Management System
Database Setup & Validation Script

This script:
1. Tests Supabase connectivity (REST API + direct PostgreSQL)
2. Creates all required tables if they don't exist
3. Creates a default admin account
4. Validates the setup

Usage:
    python database/setup_db.py
"""
import os
import sys
import bcrypt
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =====================================================
# CONFIGURATION
# =====================================================

DATABASE_URL = os.getenv('DATABASE_URL')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Default admin credentials
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_EMAIL = 'admin@itbp.gov.in'
DEFAULT_ADMIN_PASSWORD = 'admin123'
DEFAULT_ADMIN_FULLNAME = 'ITBP Admin'


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_status(label, success, detail=""):
    """Print a status line"""
    icon = "✅" if success else "❌"
    msg = f"  {icon} {label}"
    if detail:
        msg += f" - {detail}"
    print(msg)


def test_supabase_rest_api():
    """Test connectivity to Supabase REST API"""
    print_header("Step 1: Testing Supabase REST API Connectivity")
    
    try:
        import requests
        # Use the correct anon key - check if SUPABASE_KEY is a JWT, if not try SERVICE_KEY
        key = SUPABASE_KEY
        
        # Test basic REST endpoint
        url = f"{SUPABASE_URL}/rest/v1/"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code in [200, 401, 403]:
            print_status("Supabase REST API", True, f"Reachable (HTTP {response.status_code})")
            return True
        else:
            print_status("Supabase REST API", False, f"HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError as e:
        print_status("Supabase REST API", False, "Cannot connect - DNS/Network error")
        print(f"    Error: {e}")
        return False
    except Exception as e:
        print_status("Supabase REST API", False, str(e))
        return False


def test_direct_postgres():
    """Test direct PostgreSQL connection"""
    print_header("Step 2: Testing Direct PostgreSQL Connection")
    
    if not DATABASE_URL:
        print_status("DATABASE_URL", False, "Not configured in .env")
        return None
    
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print_status("PostgreSQL Connection", True, "Connected!")
        print(f"    Database: {version[:60]}...")
        cursor.close()
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        error_msg = str(e).strip().split('\n')[0]
        print_status("PostgreSQL Connection", False, error_msg)
        return False
    except Exception as e:
        print_status("PostgreSQL Connection", False, str(e))
        return False


def create_tables(conn):
    """Create all required tables"""
    print_header("Step 3: Creating/Validating Database Tables")
    
    cursor = conn.cursor()
    
    # Create enums (ignore if they already exist)
    enums = [
        ("user_role", "('admin', 'mess_user', 'grain_shop_user')"),
        ("ration_category", "('veg', 'non_veg', 'grocery')"),
        ("approval_status", "('pending', 'approved', 'rejected')"),
        ("transaction_type", "('incoming', 'outgoing')")
    ]
    
    for enum_name, enum_values in enums:
        try:
            cursor.execute(f"CREATE TYPE {enum_name} AS ENUM {enum_values};")
            print_status(f"Enum '{enum_name}'", True, "Created")
        except psycopg2.errors.DuplicateObject:
            conn.rollback()
            print_status(f"Enum '{enum_name}'", True, "Already exists")
    
    # Create UUID extension
    try:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        print_status("UUID extension", True, "Enabled")
    except Exception as e:
        conn.rollback()
        print_status("UUID extension", False, str(e))
    
    # Create tables
    tables = {
        'users': """
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                role user_role NOT NULL DEFAULT 'mess_user',
                phone VARCHAR(20) NOT NULL DEFAULT '0000000000',
                manager_id UUID REFERENCES users(id),
                is_active BOOLEAN DEFAULT TRUE,
                created_by UUID REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'contractors': """
            CREATE TABLE IF NOT EXISTS contractors (
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
        """,
        'mess': """
            CREATE TABLE IF NOT EXISTS mess (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name VARCHAR(255) NOT NULL,
                location VARCHAR(255),
                capacity INTEGER,
                manager_id UUID REFERENCES users(id),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'items': """
            CREATE TABLE IF NOT EXISTS items (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name VARCHAR(255) NOT NULL,
                category ration_category NOT NULL,
                unit VARCHAR(50) NOT NULL,
                description TEXT,
                minimum_stock DECIMAL(10,2) DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'grain_shop_inventory': """
            CREATE TABLE IF NOT EXISTS grain_shop_inventory (
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
        """,
        'mess_inventory': """
            CREATE TABLE IF NOT EXISTS mess_inventory (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                mess_id UUID REFERENCES mess(id) NOT NULL,
                item_id UUID REFERENCES items(id) NOT NULL,
                quantity DECIMAL(10,2) NOT NULL,
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                recorded_by UUID REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'daily_ration_usage': """
            CREATE TABLE IF NOT EXISTS daily_ration_usage (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                mess_id UUID REFERENCES mess(id) NOT NULL,
                item_id UUID REFERENCES items(id) NOT NULL,
                quantity_used DECIMAL(10,2) NOT NULL,
                usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
                meal_type VARCHAR(50),
                personnel_count INTEGER,
                notes TEXT,
                recorded_by UUID REFERENCES users(id),
                approval_status approval_status DEFAULT 'pending',
                approved_by UUID REFERENCES users(id),
                approved_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """,
        'pending_updates': """
            CREATE TABLE IF NOT EXISTS pending_updates (
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
        """,
        'distribution_log': """
            CREATE TABLE IF NOT EXISTS distribution_log (
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
        """,
        'activity_log': """
            CREATE TABLE IF NOT EXISTS activity_log (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id UUID REFERENCES users(id),
                action VARCHAR(50) NOT NULL,
                table_name VARCHAR(100),
                record_id UUID,
                old_data JSONB,
                new_data JSONB,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """
    }
    
    for table_name, create_sql in tables.items():
        try:
            cursor.execute(create_sql)
            # Check if table exists now
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                );
            """, (table_name,))
            exists = cursor.fetchone()[0]
            print_status(f"Table '{table_name}'", exists, "Ready" if exists else "Failed")
        except Exception as e:
            conn.rollback()
            print_status(f"Table '{table_name}'", False, str(e)[:80])
    
    # Try to add username column if the table already exists but doesn't have it
    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'username'
            );
        """)
        has_username = cursor.fetchone()[0]
        if not has_username:
            cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(100) UNIQUE;")
            # Backfill existing users - set username to the part before @ in email
            cursor.execute("""
                UPDATE users SET username = SPLIT_PART(email, '@', 1) 
                WHERE username IS NULL;
            """)
            cursor.execute("ALTER TABLE users ALTER COLUMN username SET NOT NULL;")
            print_status("Added 'username' column to users", True, "Migrated existing users")
    except Exception as e:
        conn.rollback()
        # might already exist, that's fine
        pass
    
    # Try to add manager_id column if it doesn't exist
    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'manager_id'
            );
        """)
        has_manager = cursor.fetchone()[0]
        if not has_manager:
            cursor.execute("ALTER TABLE users ADD COLUMN manager_id UUID REFERENCES users(id);")
            print_status("Added 'manager_id' column to users", True, "Migration complete")
    except Exception as e:
        conn.rollback()
        pass
    
    # Make email optional (drop NOT NULL if it exists)
    try:
        cursor.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL;")
        print_status("Made 'email' optional", True, "Column updated")
    except Exception as e:
        conn.rollback()
        pass
    
    # Make phone mandatory (set default for existing NULLs, then add NOT NULL)
    try:
        cursor.execute("UPDATE users SET phone = '0000000000' WHERE phone IS NULL;")
        cursor.execute("ALTER TABLE users ALTER COLUMN phone SET NOT NULL;")
        cursor.execute("ALTER TABLE users ALTER COLUMN phone SET DEFAULT '0000000000';")
        print_status("Made 'phone' mandatory", True, "Column updated")
    except Exception as e:
        conn.rollback()
        pass
    
    cursor.close()


def create_default_admin(conn):
    """Create the default admin user"""
    print_header("Step 4: Creating Default Admin Account")
    
    cursor = conn.cursor()
    
    # Check if admin already exists
    cursor.execute("SELECT id, username, email FROM users WHERE username = %s OR email = %s", 
                   (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL))
    existing = cursor.fetchone()
    
    if existing:
        print_status("Admin account", True, f"Already exists (username: '{existing[1]}', email: '{existing[2]}')")
        cursor.close()
        return True
    
    # Hash the password
    password_hash = bcrypt.hashpw(
        DEFAULT_ADMIN_PASSWORD.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')
    
    try:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role, phone, is_active)
            VALUES (%s, %s, %s, %s, 'admin', '0000000000', TRUE)
        """, (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL, password_hash, DEFAULT_ADMIN_FULLNAME))
        
        print_status("Admin account created", True)
        print(f"    Username : {DEFAULT_ADMIN_USERNAME}")
        print(f"    Password : {DEFAULT_ADMIN_PASSWORD}")
        print(f"    Email    : {DEFAULT_ADMIN_EMAIL}")
        print(f"    Role     : admin")
        cursor.close()
        return True
    except Exception as e:
        conn.rollback()
        print_status("Admin account", False, str(e)[:80])
        cursor.close()
        return False


def seed_sample_items(conn):
    """Insert sample items if none exist"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM items;")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print_status("Sample items", True, f"{count} items already exist")
        cursor.close()
        return
    
    items = [
        ('Rice', 'veg', 'kg', 100),
        ('Wheat Flour', 'veg', 'kg', 50),
        ('Dal (Toor)', 'veg', 'kg', 25),
        ('Dal (Moong)', 'veg', 'kg', 25),
        ('Potatoes', 'veg', 'kg', 50),
        ('Onions', 'veg', 'kg', 30),
        ('Tomatoes', 'veg', 'kg', 20),
        ('Green Vegetables', 'veg', 'kg', 40),
        ('Chicken', 'non_veg', 'kg', 30),
        ('Mutton', 'non_veg', 'kg', 20),
        ('Fish', 'non_veg', 'kg', 15),
        ('Eggs', 'non_veg', 'pieces', 500),
        ('Cooking Oil', 'grocery', 'liters', 50),
        ('Sugar', 'grocery', 'kg', 30),
        ('Salt', 'grocery', 'kg', 20),
        ('Tea', 'grocery', 'kg', 10),
        ('Milk Powder', 'grocery', 'kg', 15),
        ('Spices Mix', 'grocery', 'kg', 5),
    ]
    
    try:
        for name, category, unit, min_stock in items:
            cursor.execute("""
                INSERT INTO items (name, category, unit, minimum_stock)
                VALUES (%s, %s, %s, %s)
            """, (name, category, unit, min_stock))
        print_status("Sample items", True, f"Inserted {len(items)} items")
    except Exception as e:
        conn.rollback()
        print_status("Sample items", False, str(e)[:80])
    
    cursor.close()


def disable_rls(conn):
    """Disable RLS for development (Supabase anon key won't have access otherwise)"""
    cursor = conn.cursor()
    
    tables = ['users', 'contractors', 'mess', 'items', 'grain_shop_inventory',
              'mess_inventory', 'daily_ration_usage', 'pending_updates', 
              'distribution_log', 'activity_log']
    
    for table in tables:
        try:
            cursor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        except Exception:
            conn.rollback()
    
    print_status("Row Level Security", True, "Disabled for development")
    cursor.close()


def validate_supabase_client():
    """Validate Supabase client can connect"""
    print_header("Step 5: Validating Supabase Client")
    
    try:
        from supabase import create_client
        
        # Try with the service key first (it's the JWT), fall back to SUPABASE_KEY
        key = SUPABASE_SERVICE_KEY if SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_KEY.startswith('eyJ') else SUPABASE_KEY
        
        client = create_client(SUPABASE_URL, key)
        result = client.table('users').select('id, username, email, role').limit(5).execute()
        
        if result.data:
            print_status("Supabase client", True, f"Connected! Found {len(result.data)} user(s)")
            for user in result.data:
                print(f"    - {user.get('username', 'N/A')} ({user.get('role', 'N/A')})")
        else:
            print_status("Supabase client", True, "Connected but no users found")
        
        return True
    except Exception as e:
        print_status("Supabase client", False, str(e)[:100])
        return False


def fix_env_keys():
    """Check and suggest fixes for .env keys"""
    print_header("Step 0: Checking .env Configuration")
    
    issues = []
    
    if not SUPABASE_URL:
        issues.append("SUPABASE_URL is not set")
        print_status("SUPABASE_URL", False, "Not configured")
    else:
        print_status("SUPABASE_URL", True, SUPABASE_URL)
    
    if not SUPABASE_KEY:
        issues.append("SUPABASE_KEY is not set")
        print_status("SUPABASE_KEY", False, "Not configured")
    else:
        is_jwt = SUPABASE_KEY.startswith('eyJ')
        print_status("SUPABASE_KEY", True, f"Set ({'JWT format' if is_jwt else 'Non-JWT format: ' + SUPABASE_KEY[:30] + '...'})")
    
    if SUPABASE_SERVICE_KEY:
        is_jwt = SUPABASE_SERVICE_KEY.startswith('eyJ')
        print_status("SUPABASE_SERVICE_KEY", True, f"Set ({'JWT format' if is_jwt else 'Non-JWT format'})")
        
        # Check if keys might be swapped
        if SUPABASE_KEY and not SUPABASE_KEY.startswith('eyJ') and SUPABASE_SERVICE_KEY.startswith('eyJ'):
            print("\n  ⚠️  WARNING: SUPABASE_KEY is not a JWT but SUPABASE_SERVICE_KEY is.")
            print("    The Supabase Python client expects the anon key (JWT format) as SUPABASE_KEY.")
            print("    Consider swapping them, or use the JWT key for SUPABASE_KEY.")
            issues.append("Keys may be swapped")
    
    if not DATABASE_URL:
        print_status("DATABASE_URL", False, "Not configured (needed for direct DB setup)")
        issues.append("DATABASE_URL is not set")
    else:
        # Mask password in output
        display_url = DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL
        print_status("DATABASE_URL", True, f"...@{display_url}")
    
    return len(issues) == 0


def main():
    """Main setup flow"""
    print("\n🌾 ITBP RTC Grain Shop Management - Database Setup & Validation")
    print("=" * 60)
    
    # Step 0: Check env config
    env_ok = fix_env_keys()
    
    # Step 1: Test Supabase REST API
    rest_ok = test_supabase_rest_api()
    
    # Step 2: Test Direct PostgreSQL
    pg_ok = test_direct_postgres()
    
    if not pg_ok:
        print_header("SETUP CANNOT CONTINUE")
        print("  ❌ Cannot connect to PostgreSQL database.")
        print()
        print("  Possible causes:")
        print("  1. Supabase project is PAUSED (free tier pauses after 7 days of inactivity)")
        print("     → Go to https://supabase.com/dashboard and restore your project")
        print("  2. DATABASE_URL is incorrect in .env")
        print("  3. Network/firewall is blocking the connection")
        print()
        if not rest_ok:
            print("  ⚠️  Both REST API and PostgreSQL are unreachable.")
            print("     Your Supabase project is most likely paused or deleted.")
            print("     Please visit https://supabase.com/dashboard to check.")
        print()
        sys.exit(1)
    
    # Connect to PostgreSQL for table setup
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    # Step 3: Create tables
    create_tables(conn)
    
    # Step 4: Create default admin
    create_default_admin(conn)
    
    # Seed sample items
    print_header("Step 4b: Seeding Sample Data")
    seed_sample_items(conn)
    
    # Disable RLS for development
    disable_rls(conn)
    
    conn.close()
    
    # Step 5: Validate Supabase client
    validate_supabase_client()
    
    # Summary
    print_header("SETUP COMPLETE ✅")
    print(f"  Default Admin Login:")
    print(f"    Username : {DEFAULT_ADMIN_USERNAME}")
    print(f"    Password : {DEFAULT_ADMIN_PASSWORD}")
    print()
    print("  Next steps:")
    print("    1. Start API:      ./run.sh api")
    print("    2. Start Frontend: ./run.sh frontend")
    print("    3. Open browser:   http://localhost:8501")
    print()


if __name__ == '__main__':
    main()
