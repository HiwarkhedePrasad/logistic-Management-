"""Consolidated logging helpers for agent and event logging."""

import json
import uuid
from datetime import datetime
from langchain_core.tools import tool
from utils.database_utils import insert_table_with_retry, get_connection

@tool
def log_agent_thinking(agent_name: str, thinking_stage: str, thought_content: str, 
                       conversation_id: str = None, session_id: str = None, 
                       model_deployment_name: str = "langchain-model",
                       user_query: str = None, 
                       agent_output: str = None, thinking_stage_output: str = None,
                       status: str = "success") -> str:
    """Logs the agent's thinking process to Supabase.
    
    Args:
        agent_name: Name of the agent 
        thinking_stage: Current thinking stage 
        thought_content: The agent's thoughts at this stage
        conversation_id: Unique ID for this conversation
        session_id: ID of the current chat session
        model_deployment_name: Name of the model
        user_query: The original user query that initiated this thinking process
        agent_output: The full agent response
        thinking_stage_output: The output of this specific thinking stage
        status: Status of this thinking step
        
    Returns:
        JSON string with the result of the logging operation
    """
    try:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        if thinking_stage_output is not None and not isinstance(thinking_stage_output, str):
            try:
                thinking_stage_output = json.dumps(thinking_stage_output)
            except Exception:
                thinking_stage_output = str(thinking_stage_output)
        
        if agent_output is not None and not isinstance(agent_output, str):
            try:
                agent_output = json.dumps(agent_output)
            except Exception:
                agent_output = str(agent_output)
        
        # Truncate to avoid extremely large text entries
        max_text_length = 50000
        if thought_content and len(thought_content) > max_text_length:
            thought_content = thought_content[:max_text_length] + "... [TRUNCATED]"
        if thinking_stage_output and len(thinking_stage_output) > max_text_length:
            thinking_stage_output = thinking_stage_output[:max_text_length] + "... [TRUNCATED]"
        if agent_output and len(agent_output) > max_text_length:
            agent_output = agent_output[:max_text_length] + "... [TRUNCATED]"
        
        try:
            insert_table_with_retry('dim_agent_thinking_log', {
                'agent_name': agent_name,
                'thinking_stage': thinking_stage,
                'thought_content': thought_content,
                'thinking_stage_output': thinking_stage_output,
                'agent_output': agent_output,
                'conversation_id': conversation_id,
                'session_id': session_id,
                'azure_agent_id': agent_name,  # Using agent_name as the identifier here
                'model_deployment_name': model_deployment_name,
                'thread_id': conversation_id,  # Thread ID logic is obsolete without Assistants API
                'user_query': user_query,
                'status': status,
                'created_date': datetime.now().isoformat()
            })
            
            return json.dumps({"success": True, "conversation_id": conversation_id})
            
        except Exception as db_error:
            print(f"Database error in log_agent_thinking: {db_error}")
            return json.dumps({
                "success": False, 
                "error": str(db_error),
                "conversation_id": conversation_id
            })
            
    except Exception as e:
        print(f"Error in log_agent_thinking: {e}")
        return json.dumps({"error": str(e)})


def log_agent_response(agent_name: str, response_content: str, 
                       conversation_id: str = None, session_id: str = None,
                       user_query: str = None) -> str:
    """Logs a complete agent response to facilitate debugging."""
    return log_agent_thinking(
        agent_name=agent_name,
        thinking_stage="complete_response",
        thought_content=f"Complete response from {agent_name}",
        conversation_id=conversation_id,
        session_id=session_id,
        user_query=user_query,
        agent_output=response_content,
        thinking_stage_output=response_content
    )


@tool
def log_agent_event(agent_name: str, action: str, result_summary: str = None, 
                conversation_id: str = None, session_id: str = None,
                user_query: str = None, agent_output: str = None) -> str:
    """Logs an agent event to the database (Supabase)."""
    try:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            
        insert_table_with_retry('dim_agent_event_log', {
            'agent_name': agent_name,
            'event_time': datetime.now().isoformat(),
            'action': action,
            'result_summary': result_summary,
            'user_query': user_query,
            'agent_output': agent_output,
            'conversation_id': conversation_id,
            'session_id': session_id,
            'event_id': str(uuid.uuid4())
        })
        
        return json.dumps({"success": True, "conversation_id": conversation_id})
        
    except Exception as e:
        print(f"Error in log_agent_event: {str(e)}")
        return json.dumps({"error": str(e)})


def log_agent_error(agent_name: str, error_type: str, error_message: str,
                    conversation_id: str = None, session_id: str = None,
                    user_query: str = None) -> str:
    """Logs an error that occurred during agent thinking."""
    return log_agent_thinking(
        agent_name=agent_name,
        thinking_stage="error",
        thought_content=f"Error type: {error_type}\nError message: {error_message}",
        conversation_id=conversation_id,
        session_id=session_id,
        user_query=user_query,
        status="error"
    )


def get_agent_thinking_logs(conversation_id: str = None, 
                           session_id: str = None, 
                           agent_name: str = None,
                           limit: int = 100) -> str:
    """Retrieves the agent thinking logs from Supabase."""
    try:
        client = get_connection()
        query = client.table('dim_agent_thinking_log').select('*')
        
        if conversation_id:
            query = query.eq('conversation_id', conversation_id)
        if session_id:
            query = query.eq('session_id', session_id)
        if agent_name:
            query = query.eq('agent_name', agent_name)
            
        # Supabase API limits and ordering
        response = query.order('created_date', desc=True).limit(limit).execute()
        return json.dumps(response.data, default=str)
        
    except Exception as e:
        print(f"Error retrieving thinking logs: {e}")
        return json.dumps({"error": str(e)})


def get_conversation_history(conversation_id: str) -> str:
    """Retrieves the conversation history for a specific conversation ID."""
    try:
        client = get_connection()
        response = client.table('dim_agent_event_log').select(
            'log_id,agent_name,event_time,action,result_summary,user_query,agent_output'
        ).eq('conversation_id', conversation_id).order('event_time', desc=False).execute()
        
        return json.dumps({"conversation_id": conversation_id, "events": response.data}, default=str)
        
    except Exception as e:
        print(f"Error in get_conversation_history: {str(e)}")
        return json.dumps({"error": str(e)})


def get_recent_conversations(limit: int = 10) -> str:
    """Retrieves a list of recent conversations."""
    try:
        # Since Supabase does not support direct GROUP BY nicely via the client,
        # we can use a custom RPC function `get_recent_conversations` that we assume
        # will be created on the Supabase side, or simulate it. For now, we'll
        # retrieve unique entries by fetching recent logs and uniquely identifying them.
        client = get_connection()
        # Fallback to an RPC call which must be defined in Supabase
        # We'll build the basic select with the Python client for now, but a true group by requires RPC.
        # So we'll call the rpc
        response = client.rpc('get_recent_conversations', {'row_limit': limit}).execute()
        
        return json.dumps({"conversations": response.data}, default=str)
        
    except Exception as e:
        print(f"Error in get_recent_conversations: {str(e)}")
        return json.dumps({"error": str(e)})