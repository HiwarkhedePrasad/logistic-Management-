"""Configuration settings for the application."""

import os
from supabase import create_client, Client

def get_supabase_client() -> Client:
    """Gets the Supabase client connection.
    
    Returns:
        Client: The Supabase client connection
        
    Raises:
        ValueError: If required environment variables are missing
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not all([supabase_url, supabase_key]):
        raise ValueError(
            "Missing required environment variables. Please set "
            "SUPABASE_URL and SUPABASE_KEY."
        )
    
    return create_client(supabase_url, supabase_key)