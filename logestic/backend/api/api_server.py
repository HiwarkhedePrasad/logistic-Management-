"""FastAPI server for the equipment schedule agent."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import os
import dotenv
import uuid
from typing import Optional, Dict, List
from datetime import datetime
import json

# Load environment variables
dotenv.load_dotenv()

from managers.chatbot_manager import ChatbotManager
from utils.database_utils import get_connection, execute_rpc_with_retry


app = FastAPI(title="Equipment Schedule Agent API")

# Add CORS middleware so the frontend can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active chatbot managers
active_managers: Dict[str, ChatbotManager] = {}


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    status: str
    response: Optional[str] = None
    error: Optional[str] = None
    session_id: str


class SessionResponse(BaseModel):
    session_id: str
    conversations: List[dict]


class SessionIdResponse(BaseModel):
    session_id: str
    user_query: str
    session_date: str


class ThinkingLogResponse(BaseModel):
    session_id: str
    conversations: List[dict]


class ThinkingLogIdResponse(BaseModel):
    session_id: str
    first_query: Optional[str] = None


class HeatmapResponse(BaseModel):
    datetime_stamp: str
    conversation_id: str
    session_id: str
    country: str
    average_risk: str
    breakdown: str = ""


class ReportResponse(BaseModel):
    session_id: str
    blob_url: str
    filename: str
    report_type: str
    created_date: str


def get_chatbot_manager(session_id: str) -> ChatbotManager:
    """Get or create a ChatbotManager for the session."""
    if session_id not in active_managers:
        active_managers[session_id] = ChatbotManager()

    return active_managers[session_id]


def validate_session(session_id: str) -> bool:
    """Validate if a session exists and is still active."""
    if not session_id:
        return False

    # Check if session exists in active managers
    if session_id not in active_managers:
        return False

    return True


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        session_id = request.session_id or str(uuid.uuid4())

        # Validate existing session
        if request.session_id and not validate_session(session_id):
            # Session expired or invalid, create new session
            session_id = str(uuid.uuid4())

        # Get or create chatbot manager
        chatbot_manager = get_chatbot_manager(session_id)

        # Process the message
        try:
            response = await asyncio.wait_for(
                chatbot_manager.process_message(session_id, request.message),
                timeout=300,
            )

            if response.get("status") == "error":
                raise HTTPException(
                    status_code=500,
                    detail=response.get("error", "Unknown error occurred"),
                )

            return ChatResponse(
                status="success",
                response=response.get("response"),
                session_id=session_id,
            )

        except asyncio.TimeoutError:
            # Clean up the timed-out session
            if session_id in active_managers:
                del active_managers[session_id]

            raise HTTPException(
                status_code=504,
                detail="Request timed out. Please try a simpler request or wait a moment before retrying.",
            )

    except Exception as e:
        # Clean up the session on error
        if session_id in active_managers:
            del active_managers[session_id]

        raise HTTPException(
            status_code=500, detail=f"Error processing chat request: {str(e)}"
        )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources when shutting down."""
    for manager in active_managers.values():
        if hasattr(manager, "cleanup_sessions"):
            await manager.cleanup_sessions(max_age_minutes=0)
    active_managers.clear()


@app.get("/api/sessions", response_model=List[SessionResponse])
async def get_sessions():
    try:
        client = get_connection()

        # Get all sessions with their events
        response = client.table('dim_agent_event_log').select(
            'session_id, conversation_id, event_time, user_query, agent_output, action'
        ).order('created_date', desc=True).execute()

        if not response.data:
            return []

        # Group by session_id, then by conversation_id
        sessions = {}
        for row in response.data:
            sid = row.get('session_id')
            cid = row.get('conversation_id')
            if sid not in sessions:
                sessions[sid] = {}
            if cid not in sessions[sid]:
                sessions[sid][cid] = {
                    'conversation_id': cid,
                    'last_interaction': row.get('event_time'),
                    'messages': []
                }
            sessions[sid][cid]['messages'].append({
                'event_time': row.get('event_time'),
                'user_query': row.get('user_query'),
                'agent_output': row.get('agent_output'),
                'action': row.get('action')
            })
            # Track max event_time
            evt = row.get('event_time')
            if evt and evt > (sessions[sid][cid].get('last_interaction') or ''):
                sessions[sid][cid]['last_interaction'] = evt

        results = []
        for sid, convs in sessions.items():
            results.append(
                SessionResponse(
                    session_id=sid,
                    conversations=list(convs.values())
                )
            )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )


@app.get("/api/session-ids", response_model=List[SessionIdResponse])
async def get_session_ids():
    try:
        client = get_connection()

        # Get sessions with their first user query
        response = client.table('dim_agent_event_log').select(
            'session_id, user_query, event_time'
        ).not_.is_('user_query', 'null').order('event_time', desc=False).execute()

        if not response.data:
            return []

        # Group by session_id and get first query + earliest date
        session_map = {}
        for row in response.data:
            sid = row.get('session_id')
            if sid not in session_map:
                session_map[sid] = {
                    'first_query': row.get('user_query', ''),
                    'session_date': row.get('event_time', ''),
                    'order_date': row.get('event_time', '')
                }

        # Sort by date descending
        sorted_sessions = sorted(
            session_map.items(),
            key=lambda x: x[1]['order_date'] or '',
            reverse=True
        )

        results = [
            SessionIdResponse(
                session_id=sid,
                user_query=data['first_query'] or '',
                session_date=data['session_date'] or '',
            )
            for sid, data in sorted_sessions
        ]

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving session IDs: {str(e)}"
        )


@app.get("/api/thinking-logs", response_model=List[ThinkingLogResponse])
async def get_thinking_logs():
    try:
        client = get_connection()

        response = client.table('dim_agent_thinking_log').select('*').order(
            'created_date', desc=True
        ).limit(500).execute()

        if not response.data:
            return []

        # Group by session_id, then conversation_id, then agent
        sessions = {}
        for row in response.data:
            sid = row.get('session_id')
            cid = row.get('conversation_id')
            agent = row.get('agent_name')

            if sid not in sessions:
                sessions[sid] = {}
            if cid not in sessions[sid]:
                sessions[sid][cid] = {
                    'conversation_id': cid,
                    'user_query': row.get('user_query'),
                    'agents': {}
                }
            if agent not in sessions[sid][cid]['agents']:
                sessions[sid][cid]['agents'][agent] = {
                    'agent_name': agent,
                    'first_appearance': row.get('created_date'),
                    'thoughts': []
                }
            sessions[sid][cid]['agents'][agent]['thoughts'].append({
                'thought_content': row.get('thought_content'),
                'thinking_stage': row.get('thinking_stage'),
                'thinking_stage_output': row.get('thinking_stage_output'),
                'created_date': row.get('created_date')
            })
            # Update user_query if this row has one
            if row.get('user_query') and not sessions[sid][cid].get('user_query'):
                sessions[sid][cid]['user_query'] = row.get('user_query')

        results = []
        for sid, convs in sessions.items():
            conversations = []
            for cid, conv_data in convs.items():
                conversations.append({
                    'conversation_id': cid,
                    'user_query': conv_data.get('user_query'),
                    'agents': list(conv_data['agents'].values())
                })
            results.append(
                ThinkingLogResponse(session_id=sid, conversations=conversations)
            )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving thinking logs: {str(e)}"
        )


@app.get("/api/thinking-log-ids", response_model=List[ThinkingLogIdResponse])
async def get_thinking_log_ids():
    try:
        client = get_connection()

        response = client.table('dim_agent_thinking_log').select(
            'session_id, user_query, created_date'
        ).not_.is_('user_query', 'null').order('created_date', desc=True).execute()

        if not response.data:
            return []

        # Get unique session_ids with their first query
        session_map = {}
        for row in response.data:
            sid = row.get('session_id')
            if sid not in session_map:
                session_map[sid] = row.get('user_query')

        results = [
            ThinkingLogIdResponse(
                session_id=sid, first_query=first_query
            )
            for sid, first_query in session_map.items()
        ]

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving thinking log IDs: {str(e)}"
        )


@app.get(
    "/api/thinking-logs-by-session-id/{session_id}", response_model=ThinkingLogResponse
)
async def get_thinking_log_by_session(session_id: str):
    try:
        client = get_connection()

        response = client.table('dim_agent_thinking_log').select('*').eq(
            'session_id', session_id
        ).order('created_date', desc=False).execute()

        if not response.data:
            return ThinkingLogResponse(session_id=session_id, conversations=[])

        # Group by conversation_id, then agent
        convs = {}
        for row in response.data:
            cid = row.get('conversation_id')
            agent = row.get('agent_name')

            if cid not in convs:
                convs[cid] = {
                    'conversation_id': cid,
                    'user_query': row.get('user_query'),
                    'agents': {}
                }
            if agent not in convs[cid]['agents']:
                convs[cid]['agents'][agent] = {
                    'agent_name': agent,
                    'first_appearance': row.get('created_date'),
                    'thoughts': []
                }
            convs[cid]['agents'][agent]['thoughts'].append({
                'thought_content': row.get('thought_content'),
                'thinking_stage': row.get('thinking_stage'),
                'thinking_stage_output': row.get('thinking_stage_output'),
                'created_date': row.get('created_date')
            })
            if row.get('user_query') and not convs[cid].get('user_query'):
                convs[cid]['user_query'] = row.get('user_query')

        conversations = []
        for cid, conv_data in convs.items():
            conversations.append({
                'conversation_id': cid,
                'user_query': conv_data.get('user_query'),
                'agents': list(conv_data['agents'].values())
            })

        return ThinkingLogResponse(session_id=session_id, conversations=conversations)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving thinking log: {str(e)}"
        )


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session_by_id(session_id: str):
    try:
        client = get_connection()

        response = client.table('dim_agent_event_log').select(
            'session_id, conversation_id, event_time, user_query, agent_output, agent_name, action'
        ).eq('session_id', session_id).order('event_time', desc=False).execute()

        if not response.data:
            raise HTTPException(
                status_code=404, detail=f"Session not found with ID: {session_id}"
            )

        # Group by conversation_id
        convs = {}
        for row in response.data:
            cid = row.get('conversation_id')
            if cid not in convs:
                convs[cid] = {
                    'conversation_id': cid,
                    'last_interaction': row.get('event_time'),
                    'messages': []
                }
            convs[cid]['messages'].append({
                'event_time': row.get('event_time'),
                'user_query': row.get('user_query'),
                'agent_output': row.get('agent_output'),
                'agent_name': row.get('agent_name'),
                'action': row.get('action')
            })
            evt = row.get('event_time')
            if evt and evt > (convs[cid].get('last_interaction') or ''):
                convs[cid]['last_interaction'] = evt

        return SessionResponse(
            session_id=session_id,
            conversations=list(convs.values())
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving session: {str(e)}"
        )


@app.get("/api/heatmap", response_model=List[HeatmapResponse])
async def get_heatmap_data(conversation_id: str, session_id: str):
    try:
        # Call the PostgreSQL function via Supabase RPC
        data = execute_rpc_with_retry(
            'get_country_risk_heatmap_data',
            {'p_conversation_id': conversation_id, 'p_session_id': session_id}
        )

        if not data:
            return []

        results = [
            HeatmapResponse(
                datetime_stamp=datetime.now().isoformat(),
                conversation_id=conversation_id,
                session_id=session_id,
                country=row.get('country', ''),
                average_risk=str(round(float(row.get('average_risk', 0)))),
                breakdown=json.dumps(row.get('breakdown', '')) if isinstance(row.get('breakdown'), (dict, list)) else str(row.get('breakdown', '')),
            )
            for row in data
        ]

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving heatmap data: {str(e)}"
        )


@app.get("/api/reports", response_model=List[ReportResponse])
async def get_reports():
    try:
        client = get_connection()

        response = client.table('fact_risk_report').select(
            'session_id, blob_url, filename, report_type, created_date'
        ).order('created_date', desc=True).execute()

        if not response.data:
            return []

        results = [
            ReportResponse(
                session_id=row.get('session_id', ''),
                blob_url=row.get('blob_url', ''),
                filename=row.get('filename', ''),
                report_type=row.get('report_type', ''),
                created_date=str(row.get('created_date', '')),
            )
            for row in response.data
        ]

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving reports: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
