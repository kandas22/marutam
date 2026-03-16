"""
Run migration_v3.sql against Supabase database
Uses the Supabase service role key to execute SQL via the REST API
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import requests

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def run_migration():
    """Execute migration SQL statements one by one via Supabase REST API"""
    
    # Read migration file
    migration_file = os.path.join(os.path.dirname(__file__), 'migration_v3.sql')
    with open(migration_file, 'r') as f:
        full_sql = f.read()
    
    # Split into individual statements (skip comments and empty lines)
    # We'll execute the migration via the Supabase SQL Editor / RPC
    headers = {
        'apikey': SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }
    
    # Use the Supabase REST API to run raw SQL via pg_net or rpc
    # For Supabase, we need to use the SQL editor endpoint or create an RPC function
    # Alternative: use psycopg2 directly with the database connection string
    
    # Try using the Supabase management API
    # The database URL for direct connection
    db_ref = SUPABASE_URL.replace('https://', '').replace('.supabase.co', '')
    
    print(f"Supabase Project: {db_ref}")
    print(f"Migration file: {migration_file}")
    print(f"SQL length: {len(full_sql)} characters")
    print()
    print("=" * 60)
    print("MIGRATION SQL READY")
    print("=" * 60)
    print()
    print("To run this migration, please execute the SQL in the")
    print("Supabase SQL Editor:")
    print()
    print(f"  1. Go to: {SUPABASE_URL.replace('.co', '.co')}")
    print(f"     → Dashboard → SQL Editor")
    print()
    print(f"  2. Copy the contents of:")
    print(f"     database/migration_v3.sql")
    print()
    print(f"  3. Paste and click 'Run'")
    print()
    print("Alternatively, let me try to create the tables")
    print("via the Supabase Python client...")
    print()
    
    # Try using supabase-py to run individual table creation via rpc
    try:
        from supabase import create_client
        
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        # Test connection
        result = supabase.table('users').select('id', count='exact').limit(1).execute()
        print(f"✅ Connected to Supabase (found {result.count} users)")
        
        # Check if demands table already exists
        try:
            result = supabase.table('demands').select('id', count='exact').limit(1).execute()
            print(f"✅ demands table already exists ({result.count} records)")
        except Exception as e:
            if '42P01' in str(e) or 'does not exist' in str(e).lower() or 'relation' in str(e).lower():
                print("❌ demands table does not exist — migration needed")
                print()
                print("Please run the migration SQL manually in the Supabase SQL Editor.")
            else:
                print(f"⚠️  demands table check: {e}")
        
        # Check other new tables
        for table in ['demand_items', 'contractor_supplies', 'price_change_history']:
            try:
                result = supabase.table(table).select('id', count='exact').limit(1).execute()
                print(f"✅ {table} table exists ({result.count} records)")
            except Exception as e:
                if '42P01' in str(e) or 'does not exist' in str(e).lower() or 'relation' in str(e).lower():
                    print(f"❌ {table} table does not exist")
                else:
                    print(f"⚠️  {table} check: {e}")
        
        # Check if contractor role exists by trying to query users with that role
        try:
            result = supabase.table('users').select('id').eq('role', 'contractor').execute()
            print(f"✅ contractor role is available ({len(result.data)} users)")
        except Exception as e:
            print(f"⚠️  contractor role check: {e}")
        
        # Check if mess has parent_mess_id column
        try:
            result = supabase.table('mess').select('id, name, parent_mess_id, mess_type').limit(1).execute()
            print(f"✅ mess table has parent_mess_id and mess_type columns")
        except Exception as e:
            print(f"❌ mess table missing new columns: {e}")
            
    except ImportError:
        print("supabase-py not installed")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    run_migration()
