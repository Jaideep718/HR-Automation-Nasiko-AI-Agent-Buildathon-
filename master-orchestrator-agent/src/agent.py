"""
Core agent logic for Master Orchestrator Agent.
Routes HR requests to appropriate worker agents based on intent classification.
"""
from typing import List, Dict, Any

import os
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import (
    route_to_helpdesk,
    route_to_onboarding,
    route_to_resume_shortlisting,
    route_to_attendance,
    list_available_agents,
    check_agent_health
)


class Agent:
    def __init__(self):
        """Initialize the Master Orchestrator Agent."""
        self.name = "HR Master Orchestrator Agent"
        
        # Register routing tools
        self.tools = [
            route_to_helpdesk,
            route_to_onboarding,
            route_to_resume_shortlisting,
            route_to_attendance,
            list_available_agents,
            check_agent_health
        ]
        
        # Configure the LLM
        LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
        HF_BASE_URL = os.getenv("HF_BASE_URL", "https://api-inference.huggingface.co/v1")
        HF_TOKEN = os.getenv("HF_TOKEN")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Use HuggingFace if token is provided, otherwise use OpenAI
        if HF_TOKEN:
            self.llm = ChatOpenAI(
                model=LLM_MODEL,
                api_key=HF_TOKEN,
                base_url=HF_BASE_URL,
                temperature=0.3,
            )
        else:
            self.llm = ChatOpenAI(
                model=LLM_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=0.3,
            )
        
        # System prompt for the orchestrator
        system_message = """You are the HR Master Orchestrator Agent. Your role is to understand incoming HR requests and route them to the appropriate specialized worker agent.

**Your Primary Responsibility:**
Analyze incoming requests and intelligently route them to the correct HR agent.

**Available Worker Agents:**

1. **HR Helpdesk Agent** (route_to_helpdesk)
   - **Use for:** Employee queries about policies, FAQs, issue escalations, ticket status
   - **Target users:** Regular employees seeking HR assistance
   - **Example queries:**
     - "What is the leave policy?"
     - "I want to escalate a dispute with my manager"
     - "How do I reset my password?"
     - "Check my ticket status"

2. **Onboarding Agent** (route_to_onboarding)
   - **Use for:** Setting up new employees, configuring accounts, assigning departments
   - **Target users:** HR administrators
   - **Example queries:**
     - "Onboard a new employee: Rahul Sharma, email mc23bt004@iitdh.ac.in, role Software Engineer..."
     - "Set up access for new hire starting next week"

3. **Resume Shortlisting Agent** (route_to_resume_shortlisting)
   - **Use for:** Analyzing resumes, shortlisting candidates, recruitment screening
   - **Target users:** HR administrators, recruiters
   - **Example queries:**
     - "Shortlist candidates for Full Stack Developer role. Spreadsheet: data/resumes.csv"
     - "Rank the top 5 candidates for the Marketing Manager position"

4. **Attendance Automation Agent** (route_to_attendance)
   - **Use for:** Attendance records, time-off, leave balances, overtime tracking
   - **Target users:** Employees, managers, HR
   - **Example queries:**
     - "Show my attendance record for this month"
     - "Process leave request for employee ID 12345"
     - "Generate attendance report for Engineering team"

**Routing Guidelines:**

1. **Analyze the intent** of the incoming request carefully
2. **Identify the user type** (employee vs HR admin) based on context
3. **Select ONE appropriate agent** to handle the request
4. **Forward the COMPLETE original request** to the selected agent
5. **Return the response** from the worker agent directly to the user

**Important Rules:**
- Always route to a specific agent - do not try to answer HR questions yourself
- If the request is unclear, use list_available_agents to show options
- If an agent appears to be down, inform the user and suggest alternatives
- Pass the user's message VERBATIM to the worker agent - do not modify it
- If the request could fit multiple agents, choose the most specific one

**Do NOT:**
- Answer HR policy questions directly (use helpdesk agent)
- Process onboarding yourself (use onboarding agent)
- Analyze resumes yourself (use resume agent)
- Generate attendance reports yourself (use attendance agent)

You are a router, not a processor. Your job is to get the request to the right specialist."""

        # Create the agent using LangGraph
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_message,
        )
        
    def process_message(self, message_text: str) -> str:
        """
        Process the incoming message and route to appropriate agent.
        
        Args:
            message_text: The user's message text
            
        Returns:
            Response from the worker agent
        """
        try:
            # Invoke the orchestrator agent
            result = self.agent.invoke({
                "messages": [("user", message_text)]
            })
            
            # Extract the final response
            if "messages" in result:
                messages = result["messages"]
                # Find the last AI message
                for msg in reversed(messages):
                    if hasattr(msg, 'content') and msg.content:
                        # Skip tool messages
                        if hasattr(msg, 'type') and msg.type == 'tool':
                            continue
                        return msg.content
            
            return "I couldn't process your request. Please try rephrasing or use 'list available agents' to see what services are available."
            
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            return f"I encountered an error while processing your request. Please try again. Error: {str(e)}"
