import threading
from config.settings import get_supabase_client

# Create a thread-local storage for connection pooling
_thread_local = threading.local()

def get_connection():
    """Gets a Supabase client from thread local storage.
    
    Returns:
        Client: The Supabase client connection
    """
    if not hasattr(_thread_local, "client") or _thread_local.client is None:
        try:
            _thread_local.client = get_supabase_client()
            print("Created new Supabase client")
        except Exception as e:
            print(f"Error connecting to Supabase: {e}")
            raise
    
    return _thread_local.client

def execute_rpc_with_retry(rpc_name: str, params=None, max_retries=3):
    """Executes a Supabase RPC data fetch with retry logic.
    
    Args:
        rpc_name: The Postgres function name
        params: Query parameters (dict)
        max_retries: Maximum number of retry attempts
        
    Returns:
        The query results data list
    """
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            client = get_connection()
            if params:
                response = client.rpc(rpc_name, params).execute()
            else:
                response = client.rpc(rpc_name).execute()
                
            return response.data
            
        except Exception as e:
            retry_count += 1
            last_error = e
            print(f"Supabase RPC query failed (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                import time
                time.sleep(0.5)
            else:
                print(f"Failed to execute RPC after {max_retries} attempts")
                raise last_error

def insert_table_with_retry(table_name: str, data: dict, max_retries=3):
    """Executes a Supabase Table Insert with retry logic.
    
    Args:
        table_name: Name of table
        data: Dict of columns/values
        max_retries: Maximum number of retry attempts
        
    Returns:
        The query results data list
    """
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            client = get_connection()
            response = client.table(table_name).insert(data).execute()
            return response.data
            
        except Exception as e:
            retry_count += 1
            last_error = e
            print(f"Supabase Insert failed (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                import time
                time.sleep(0.5)
            else:
                print(f"Failed to execute Insert after {max_retries} attempts")
                raise last_error