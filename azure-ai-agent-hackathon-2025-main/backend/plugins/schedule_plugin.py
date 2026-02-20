"""Equipment schedule plugin for schedule management."""

import json
from langchain_core.tools import tool
from utils.database_utils import execute_rpc_with_retry

@tool
def get_schedule_comparison_data() -> str:
    """Retrieves equipment schedule comparison data for analysis"""
    try:
        print("Called get_schedule_comparison_data (LangChain Tool)")
        
        # Call the Supabase Postgres RPC function
        results = execute_rpc_with_retry('get_schedule_comparison_data')
        
        print(f"RPC returned {len(results) if results else 0} rows")
        
        # Return as JSON string
        return json.dumps(results, default=str) if results else "[]"
        
    except Exception as e:
        print(f"Error in get_schedule_comparison_data: {str(e)}")
        return json.dumps({"error": str(e)})