"""Automated workflow manager using LangGraph."""

import uuid
import asyncio
import json
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage

from managers.chatbot_manager import ChatbotManager


class AutomatedWorkflowManager:
    """Manages the automated workflow for schedule analysis."""
    
    def __init__(self, connection_string=None):
        """Initialize the workflow manager.
        
        Args:
            connection_string: Legacy parameter, kept for compatibility. Not used.
        """
        self.chatbot_manager = ChatbotManager()
    
    async def run_workflow(self) -> dict:
        """Runs the automated schedule analysis workflow.
        
        Returns:
            dict: Result of the workflow execution
        """
        try:
            session_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            workflow_run_id = str(uuid.uuid4())
            
            # Run the schedule analysis through the chatbot manager
            result = await self.chatbot_manager.process_message(
                session_id=session_id,
                message="Analyze the current equipment schedule and generate a comprehensive risk report."
            )
            
            if result.get("status") == "success":
                return {
                    "status": "success",
                    "report": result.get("response", ""),
                    "workflow_run_id": workflow_run_id,
                    "session_id": session_id,
                    "conversation_id": result.get("conversation_id"),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Unknown error"),
                    "workflow_run_id": workflow_run_id
                }
                
        except Exception as e:
            logging.error(f"Error running automated workflow: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e),
                "workflow_run_id": workflow_run_id if 'workflow_run_id' in locals() else None
            }
