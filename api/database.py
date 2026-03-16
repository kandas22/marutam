"""
Database connection and Supabase client configuration
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class Database:
    """Singleton database connection class"""
    _instance = None
    _client: Client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Supabase client"""
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not url:
            raise ValueError("SUPABASE_URL must be set in environment variables")
        
        # Supabase Python client expects a JWT key (starts with 'eyJ')
        # If SUPABASE_KEY is not a JWT, try using SUPABASE_SERVICE_KEY
        if key and key.startswith('eyJ'):
            effective_key = key
        elif service_key and service_key.startswith('eyJ'):
            print("⚠️  SUPABASE_KEY is not a JWT. Using SUPABASE_SERVICE_KEY instead.")
            effective_key = service_key
        elif key:
            effective_key = key
        else:
            raise ValueError("No valid Supabase key found. Set SUPABASE_KEY or SUPABASE_SERVICE_KEY.")
        
        self._client = create_client(url, effective_key)
    
    @property
    def client(self) -> Client:
        """Get the Supabase client"""
        return self._client
    
    def get_service_client(self) -> Client:
        """Get Supabase client with service role key for admin operations"""
        url = os.getenv('SUPABASE_URL')
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not service_key:
            # Fall back to regular key if service key not available
            return self._client
        
        return create_client(url, service_key)


def get_db() -> Client:
    """Get database client instance"""
    return Database().client


def get_service_db() -> Client:
    """Get service database client instance"""
    return Database().get_service_client()
