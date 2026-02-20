"""LangGraph implementation for equipment schedule chatbot."""

import uuid
import asyncio
import json
import logging
from typing import Dict, Any, List, TypedDict, Annotated, Sequence, Literal
from datetime import datetime
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import AzureChatOpenAI
from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent

import os

from plugins.schedule_plugin import get_schedule_comparison_data
from plugins.risk_plugin import calculate_risk_percentage, categorize_risk
from plugins.logging_plugin import log_agent_thinking, log_agent_event, log_agent_response
from plugins.report_file_plugin import save_report_to_file
from plugins.political_risk_json_plugin import convert_to_json, store_political_json_output_agent_event, extract_citations

from agents.agent_definitions import (
    SCHEDULER_AGENT, get_scheduler_agent_instructions,
    REPORTING_AGENT, get_reporting_agent_instructions,
    ASSISTANT_AGENT, get_assistant_agent_instructions,
    POLITICAL_RISK_AGENT, get_political_risk_agent_instructions,
    TARIFF_RISK_AGENT, get_tariff_risk_agent_instructions,
    LOGISTICS_RISK_AGENT, get_logistics_risk_agent_instructions
)

def add_messages(left: list, right: list):
    """Message reducer func."""
    return left + right

class AgentState(TypedDict):
    """The state of the multi-agent graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    conversation_id: str
    next_node: str

class ChatbotManager:
    def __init__(self):
        try:
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
            self.llm = AzureChatOpenAI(
                azure_deployment=deployment_name,
                api_version="2024-02-15-preview",
                temperature=0,
            )
        except Exception as e:
            print(f"Error initializing AzureChatOpenAI: {e}")
            self.llm = None
            
        self.search_tool = DuckDuckGoSearchResults()
        
        # Tools for each agent
        self.scheduler_tools = [get_schedule_comparison_data, calculate_risk_percentage, categorize_risk, log_agent_thinking]
        self.political_tools = [self.search_tool, convert_to_json, store_political_json_output_agent_event, extract_citations, log_agent_thinking]
        self.tariff_tools = [self.search_tool, log_agent_thinking]
        self.logistics_tools = [self.search_tool, log_agent_thinking]
        self.reporting_tools = [save_report_to_file, log_agent_thinking]
        self.assistant_tools = [log_agent_thinking]
        
        self.graph = self._build_graph()
        self.sessions = {}
        
    def _build_graph(self):
        """Build the LangGraph state machine."""
        
        # Define the nodes
        def create_agent(llm, tools, system_prompt):
            if llm is None:
                return None
            return create_react_agent(llm, tools, state_modifier=system_prompt)
            
        scheduler = create_agent(self.llm, self.scheduler_tools, get_scheduler_agent_instructions())
        political = create_agent(self.llm, self.political_tools, get_political_risk_agent_instructions())
        tariff = create_agent(self.llm, self.tariff_tools, get_tariff_risk_agent_instructions())
        logistics = create_agent(self.llm, self.logistics_tools, get_logistics_risk_agent_instructions())
        reporting = create_agent(self.llm, self.reporting_tools, get_reporting_agent_instructions())
        assistant = create_agent(self.llm, self.assistant_tools, get_assistant_agent_instructions())
        
        async def run_scheduler(state: AgentState):
            if not scheduler: return {"messages": [AIMessage(content="Agent not available")]}
            result = await scheduler.ainvoke({"messages": state["messages"]})
            log_agent_event.invoke({
                "agent_name": SCHEDULER_AGENT, 
                "action": "Generated schedule analysis", 
                "conversation_id": state["conversation_id"], 
                "session_id": state["session_id"],
                "agent_output": result["messages"][-1].content
            })
            return {"messages": [AIMessage(content=f"SCHEDULER_AGENT > {result['messages'][-1].content}")]}
            
        async def run_political(state: AgentState):
            if not political: return {"messages": [AIMessage(content="Agent not available")]}
            result = await political.ainvoke({"messages": state["messages"]})
            log_agent_event.invoke({
                "agent_name": POLITICAL_RISK_AGENT, 
                "action": "Generated political risk analysis", 
                "conversation_id": state["conversation_id"], 
                "session_id": state["session_id"],
                "agent_output": result["messages"][-1].content
            })
            return {"messages": [AIMessage(content=f"POLITICAL_RISK_AGENT > {result['messages'][-1].content}")]}

        async def run_tariff(state: AgentState):
            if not tariff: return {"messages": [AIMessage(content="Agent not available")]}
            result = await tariff.ainvoke({"messages": state["messages"]})
            return {"messages": [AIMessage(content=f"TARIFF_RISK_AGENT > {result['messages'][-1].content}")]}

        async def run_logistics(state: AgentState):
            if not logistics: return {"messages": [AIMessage(content="Agent not available")]}
            result = await logistics.ainvoke({"messages": state["messages"]})
            return {"messages": [AIMessage(content=f"LOGISTICS_RISK_AGENT > {result['messages'][-1].content}")]}

        async def run_reporting(state: AgentState):
            if not reporting: return {"messages": [AIMessage(content="Agent not available")]}
            result = await reporting.ainvoke({"messages": state["messages"]})
            return {"messages": [AIMessage(content=f"REPORTING_AGENT > {result['messages'][-1].content}")]}

        async def run_assistant(state: AgentState):
            if not assistant: return {"messages": [AIMessage(content="Agent not available")]}
            result = await assistant.ainvoke({"messages": state["messages"]})
            return {"messages": [AIMessage(content=f"ASSISTANT_AGENT > {result['messages'][-1].content}")]}
            
        # Router node
        async def router(state: AgentState) -> dict:
            last_message = state["messages"][-1].content.lower()
            
            if "political" in last_message:
                return {"next_node": POLITICAL_RISK_AGENT}
            elif "tariff" in last_message:
                return {"next_node": TARIFF_RISK_AGENT}
            elif "logistics" in last_message or "shipping" in last_message:
                return {"next_node": LOGISTICS_RISK_AGENT}
            elif "schedule" in last_message or "risk" in last_message:
                return {"next_node": SCHEDULER_AGENT}
            else:
                return {"next_node": ASSISTANT_AGENT}
                
        def route_after_router(state: AgentState):
            return state["next_node"]
            
        workflow = StateGraph(AgentState)
        
        workflow.add_node("router", router)
        workflow.add_node(SCHEDULER_AGENT, run_scheduler)
        workflow.add_node(POLITICAL_RISK_AGENT, run_political)
        workflow.add_node(TARIFF_RISK_AGENT, run_tariff)
        workflow.add_node(LOGISTICS_RISK_AGENT, run_logistics)
        workflow.add_node(REPORTING_AGENT, run_reporting)
        workflow.add_node(ASSISTANT_AGENT, run_assistant)
        
        workflow.add_edge(START, "router")
        
        workflow.add_conditional_edges(
            "router",
            route_after_router,
            {
                SCHEDULER_AGENT: SCHEDULER_AGENT,
                POLITICAL_RISK_AGENT: SCHEDULER_AGENT, # Requires baseline data first
                TARIFF_RISK_AGENT: SCHEDULER_AGENT,
                LOGISTICS_RISK_AGENT: SCHEDULER_AGENT,
                ASSISTANT_AGENT: ASSISTANT_AGENT
            }
        )
        
        def route_after_scheduler(state: AgentState):
            first_msg_idx = -1
            for i, msg in reversed(list(enumerate(state["messages"]))):
                if isinstance(msg, HumanMessage):
                    first_msg_idx = i
                    break
            
            if first_msg_idx >= 0:
                first_msg = state["messages"][first_msg_idx].content.lower()
                if "political" in first_msg: return POLITICAL_RISK_AGENT
                if "tariff" in first_msg: return TARIFF_RISK_AGENT
                if "logistic" in first_msg or "shipping" in first_msg: return LOGISTICS_RISK_AGENT
                if "report" in first_msg: return REPORTING_AGENT
            return END
            
        workflow.add_conditional_edges(
            SCHEDULER_AGENT,
            route_after_scheduler,
            {
                POLITICAL_RISK_AGENT: POLITICAL_RISK_AGENT,
                TARIFF_RISK_AGENT: TARIFF_RISK_AGENT,
                LOGISTICS_RISK_AGENT: LOGISTICS_RISK_AGENT,
                REPORTING_AGENT: REPORTING_AGENT,
                END: END
            }
        )
        
        workflow.add_edge(POLITICAL_RISK_AGENT, REPORTING_AGENT)
        workflow.add_edge(TARIFF_RISK_AGENT, REPORTING_AGENT)
        workflow.add_edge(LOGISTICS_RISK_AGENT, REPORTING_AGENT)
        
        workflow.add_edge(REPORTING_AGENT, END)
        workflow.add_edge(ASSISTANT_AGENT, END)
        
        return workflow.compile()

    async def initialize_session(self, session_id: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "conversation_id": str(uuid.uuid4()),
                "messages": []
            }
        return self.sessions[session_id]
        
    async def cleanup_sessions(self, max_age_minutes=0):
        self.sessions.clear()

    async def process_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Main entry point for API chat processing."""
        try:
            session = await self.initialize_session(session_id)
            conversation_id = session["conversation_id"]
            
            input_message = HumanMessage(content=message)
            state = {
                "messages": session["messages"] + [input_message],
                "session_id": session_id,
                "conversation_id": conversation_id,
                "next_node": ""
            }
            
            # Log user query
            log_agent_event.invoke({
                "agent_name": "USER",
                "action": "User Query",
                "user_query": message,
                "conversation_id": conversation_id,
                "session_id": session_id
            })
            
            # Form final result
            final_state = await self.graph.ainvoke(state)
            
            # The last message is the response
            final_response = final_state["messages"][-1].content
            
            session["messages"].append(input_message)
            session["messages"].append(AIMessage(content=final_response))
            
            return {
                "status": "success",
                "response": final_response,
                "conversation_id": conversation_id
            }
            
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }