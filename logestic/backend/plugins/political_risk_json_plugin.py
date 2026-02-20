"""Plugin for converting political risk output to standardized JSON."""

import json
import uuid
import re
from datetime import datetime
from langchain_core.tools import tool
from utils.database_utils import insert_table_with_retry

def convert_to_json_helper(risk_analysis: str) -> str:
    """Convert political risk analysis to standardized JSON format."""
    try:
        # Initialize the structure
        result = {
            "political_risks": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Extract from markdown table format
        table_pattern = r"\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
        matches = re.findall(table_pattern, risk_analysis)
        
        for match in matches:
            if len(match) >= 9:
                country = match[0].strip()
                political_type = match[1].strip()
                risk_info = match[2].strip()
                likelihood = match[3].strip()
                likelihood_reasoning = match[4].strip()
                pub_date = match[5].strip()
                citation_title = match[6].strip()
                source_name = match[7].strip()
                url = match[8].strip()
                
                if country.lower() == "country" and "political type" in political_type.lower():
                    continue
                
                risk_entry = {
                    "country": country,
                    "political_type": political_type,
                    "risk_information": risk_info,
                    "likelihood": int(likelihood) if likelihood.isdigit() else 0,
                    "likelihood_reasoning": likelihood_reasoning,
                    "publication_date": pub_date,
                    "citation_title": citation_title,
                    "citation_name": source_name,
                    "citation_url": url
                }
                result["political_risks"].append(risk_entry)
        
        query_match = re.search(r'query:\s*"([^"]+)"', risk_analysis, re.IGNORECASE)
        if query_match:
            result["search_query"] = query_match.group(1)
        else:
            query_match = re.search(r'using the query:?\s*"([^"]+)"', risk_analysis, re.IGNORECASE)
            if query_match:
                result["search_query"] = query_match.group(1)
        
        results_match = re.search(r'A total of (\d+) search results', risk_analysis)
        if results_match:
            result["search_results_count"] = int(results_match.group(1))
        
        impact_match = re.search(r'Equipment Impact Analysis.*?([\s\S]*?)(?=###|\Z)', risk_analysis, re.DOTALL)
        if impact_match:
            result["equipment_impact"] = impact_match.group(1).strip()
        
        recommendations_match = re.search(r'Mitigation Recommendations.*?([\s\S]*?)(?=###|\Z)', risk_analysis, re.DOTALL)
        if recommendations_match:
            result["mitigation_recommendations"] = recommendations_match.group(1).strip()
        
        analysis_match = re.search(r'Analysis Description.*?([\s\S]*?)(?=###|\Z)', risk_analysis, re.DOTALL)
        if analysis_match:
            result["analysis_description"] = analysis_match.group(1).strip()
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        print(f"Error converting political risk analysis: {e}")
        return json.dumps({
            "error": str(e),
            "political_risks": [],
            "timestamp": datetime.now().isoformat()
        })

@tool
def convert_to_json(risk_analysis: str) -> str:
    """Convert political risk analysis to JSON format"""
    return convert_to_json_helper(risk_analysis)

@tool
def store_political_json_output_agent_event(risk_analysis: str, agent_name: str, conversation_id: str, session_id: str) -> str:
    """Store political risk JSON in agent event log"""
    try:
        json_data = convert_to_json_helper(risk_analysis)
        event_id = str(uuid.uuid4())
        
        # Insert using Supabase helper
        insert_table_with_retry('dim_agent_event_log', {
            'event_id': event_id,
            'agent_name': agent_name,
            'event_time': datetime.now().isoformat(),
            'action': "Political Risk JSON Data",
            'result_summary': f"Structured JSON data with {len(json.loads(json_data).get('political_risks', []))} political risks",
            'user_query': None,
            'agent_output': json_data,
            'conversation_id': conversation_id,
            'session_id': session_id
        })
        
        return json.dumps({
            "success": True,
            "message": "Political risk JSON data stored in agent event log",
            "event_id": event_id,
            "json_data": json.loads(json_data)
        })
        
    except Exception as e:
        print(f"Error storing political risk JSON: {e}")
        return json.dumps({
            "error": str(e),
            "message": "Failed to store political risk JSON in event log"
        })

@tool
def extract_citations(risk_analysis: str) -> str:
    """Extract citations from political risk analysis."""
    try:
        citations = []
        
        table_pattern = r"\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
        matches = re.findall(table_pattern, risk_analysis)
        
        for match in matches:
            if len(match) >= 9:
                country = match[0].strip()
                political_type = match[1].strip()
                risk_info = match[2].strip()
                pub_date = match[5].strip()
                citation_title = match[6].strip()
                source_name = match[7].strip()
                url = match[8].strip()
                
                if country.lower() == "country" and "political type" in political_type.lower():
                    continue
                
                citation = {
                    "title": citation_title,
                    "source": source_name,
                    "url": url,
                    "publication_date": pub_date,
                    "country": country,
                    "risk_type": political_type,
                    "risk_info": risk_info
                }
                
                if not any(c.get("url") == url and c.get("title") == citation_title for c in citations):
                    citations.append(citation)
        
        return json.dumps({
            "citations": citations,
            "count": len(citations),
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        print(f"Error extracting citations: {e}")
        return json.dumps({"error": str(e), "citations": [], "count": 0})

