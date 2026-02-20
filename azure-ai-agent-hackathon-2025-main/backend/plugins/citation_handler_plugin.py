"""Plugin for retrieving and formatting citations from search results."""

import json
import re
from langchain_core.tools import tool


class CitationLoggerPlugin:
    """A plugin for formatting and managing citations from search results."""
    
    def __init__(self):
        """Initialize the plugin."""
        self._cached_citations = {}  # Cache citations by conversation_id
    
    def cache_citations(self, conversation_id: str, citations: list):
        """Cache citations for a conversation.
        
        Args:
            conversation_id: The conversation ID
            citations: List of citation dictionaries
        """
        self._cached_citations[conversation_id] = citations
    
    def get_cached_citations(self, conversation_id: str) -> list:
        """Get cached citations for a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            list: List of citation dictionaries
        """
        return self._cached_citations.get(conversation_id, [])
    
    def format_citations_as_markdown(self, citations: list) -> str:
        """Format citations as markdown.
        
        Args:
            citations: List of citation dictionaries
            
        Returns:
            str: Formatted citation section as markdown
        """
        if not citations:
            return "### References\n\nNo citations available."
            
        citation_section = "### References\n\n"
        
        for i, citation in enumerate(citations):
            title = citation.get("title", "Unknown Source")
            url = citation.get("url", "#")
            source = citation.get("source", "Unknown")
            
            citation_section += f'{i+1}. ["{title}" - {source}]({url})\n\n'
        
        return citation_section
    
    def extract_source_from_title(self, title: str) -> str:
        """Extract the source name from a citation title.
        
        Args:
            title: The citation title
            
        Returns:
            str: The extracted source name
        """
        # Many citation titles follow the format: "Title - Source, Date"
        if " - " in title:
            parts = title.split(" - ")
            if len(parts) > 1:
                source_part = parts[-1].strip()
                # Further extract if there's a comma with date
                if "," in source_part:
                    return source_part.split(",")[0].strip()
                return source_part
        
        # Default to returning the title itself if no clear source
        return title
    
    def enhance_output_with_citations(self, agent_output: str, citations: list) -> str:
        """Enhances the output by adding proper citations.
        
        Args:
            agent_output: The agent's output content
            citations: List of citation dictionaries
            
        Returns:
            str: Enhanced output with proper citations
        """
        try:
            if not citations:
                return agent_output
            
            # Check if the output already has a References section
            if "### References" in agent_output:
                # Replace the existing References section
                pattern = r'### References.*?(?=###|\Z)'
                references_section = self.format_citations_as_markdown(citations)
                enhanced_output = re.sub(pattern, references_section, agent_output, flags=re.DOTALL)
                return enhanced_output
            else:
                # Add the References section at the end
                references_section = self.format_citations_as_markdown(citations)
                
                if not agent_output.endswith("\n\n"):
                    enhanced_output = agent_output + "\n\n" + references_section
                else:
                    enhanced_output = agent_output + references_section
                
                return enhanced_output
                
        except Exception as e:
            print(f"Error enhancing output with citations: {e}")
            return agent_output


@tool
def get_formatted_citations(citations_json: str) -> str:
    """Format citations list as markdown.
    
    Args:
        citations_json: JSON string containing a list of citation objects
        
    Returns:
        str: JSON string with formatted citations
    """
    try:
        citations = json.loads(citations_json) if isinstance(citations_json, str) else citations_json
        plugin = CitationLoggerPlugin()
        markdown = plugin.format_citations_as_markdown(citations)
        
        return json.dumps({
            "success": True,
            "citation_count": len(citations),
            "citations": citations,
            "markdown": markdown
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "success": False,
            "citation_count": 0,
            "citations": [],
            "markdown": "### References\n\nUnable to retrieve citations."
        })


@tool
def enhance_political_risk_output(agent_output: str, citations_json: str) -> str:
    """Enhances political risk output by adding proper citations.
    
    Args:
        agent_output: The agent's output content
        citations_json: JSON string containing a list of citation objects
        
    Returns:
        str: Enhanced output with proper citations
    """
    try:
        citations = json.loads(citations_json) if isinstance(citations_json, str) else citations_json
        plugin = CitationLoggerPlugin()
        return plugin.enhance_output_with_citations(agent_output, citations)
    except Exception as e:
        print(f"Error enhancing political risk output: {e}")
        return agent_output