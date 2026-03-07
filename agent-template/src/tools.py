"""
Tools for the agent.
Define your LangChain tools here.
"""
from typing import List, Dict, Any
from langchain_core.tools import tool

# Example tool
@tool
def example_tool(param1: str, param2: int) -> str:
    """
    Example tool description.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    """
    return f"Executed example_tool with {param1} and {param2}"
