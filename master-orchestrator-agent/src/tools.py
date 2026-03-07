"""
Tools for the Master Orchestrator Agent.
These tools allow routing requests to worker agents via HTTP.
"""
import os
import json
import uuid
import logging
import httpx
from typing import Optional
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("master-orchestrator-agent")

# Worker agent URLs - configurable via environment variables
HR_HELPDESK_URL = os.getenv("HR_HELPDESK_URL", "http://hr-helpdesk-agent:5000")
ONBOARDING_AGENT_URL = os.getenv("ONBOARDING_AGENT_URL", "http://onboarding-agent:5000")
RESUME_SHORTLIST_URL = os.getenv("RESUME_SHORTLIST_URL", "http://resume-shortlisting-agent:5000")
ATTENDANCE_AGENT_URL = os.getenv("ATTENDANCE_AGENT_URL", "http://attendance-agent:5000")

# Timeout for agent requests (seconds)
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "120"))


def _call_worker_agent(agent_url: str, message: str, session_id: Optional[str] = None) -> str:
    """
    Internal helper to call a worker agent via A2A JSON-RPC protocol.
    
    Args:
        agent_url: Base URL of the worker agent
        message: User message to send
        session_id: Optional session ID for context
        
    Returns:
        Response text from the worker agent
    """
    request_id = str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())
    
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/send",
        "params": {
            "session_id": session_id,
            "message": {
                "role": "user",
                "parts": [
                    {"kind": "text", "text": message}
                ]
            }
        }
    }
    
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            response = client.post(agent_url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from A2A response
            if "result" in result and "artifacts" in result["result"]:
                artifacts = result["result"]["artifacts"]
                if artifacts and "parts" in artifacts[0]:
                    parts = artifacts[0]["parts"]
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            
            # Fallback: return raw response
            return json.dumps(result, indent=2)
            
    except httpx.TimeoutException:
        logger.error(f"Request to {agent_url} timed out after {AGENT_TIMEOUT}s")
        return f"Error: Request to worker agent timed out. Please try again."
    except httpx.HTTPError as e:
        logger.error(f"HTTP error calling {agent_url}: {e}")
        return f"Error: Could not reach worker agent. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Error calling worker agent at {agent_url}: {e}")
        return f"Error: Unexpected error communicating with worker agent. Details: {str(e)}"


@tool
def route_to_helpdesk(query: str) -> str:
    """
    Route employee queries to the HR Helpdesk Agent.
    Use this for:
    - Employee questions about HR policies (leave, benefits, remote work, expenses)
    - FAQ queries (password reset, payroll, vacation balance, org chart, holidays)
    - Issue escalations (complaints, disputes, harassment reports)
    - Ticket status checks
    
    Args:
        query: The employee's question or request
        
    Returns:
        Response from the HR Helpdesk Agent
    """
    logger.info(f"Routing to HR Helpdesk Agent: {query[:100]}...")
    return _call_worker_agent(HR_HELPDESK_URL, query)


@tool
def route_to_onboarding(query: str) -> str:
    """
    Route onboarding requests to the Onboarding Agent.
    Use this for HR administrators to:
    - Onboard new employees
    - Set up employee accounts and access
    - Assign managers and departments
    - Configure start dates and locations
    
    Example query: "Onboard a new employee: Rahul Sharma, email mc23bt004@iitdh.ac.in, 
    role Software Engineer, department Engineering, manager Priya Patel, 
    start date 2026-04-01, location Bangalore"
    
    Args:
        query: The onboarding request with employee details
        
    Returns:
        Response from the Onboarding Agent
    """
    logger.info(f"Routing to Onboarding Agent: {query[:100]}...")
    return _call_worker_agent(ONBOARDING_AGENT_URL, query)


@tool
def route_to_resume_shortlisting(query: str) -> str:
    """
    Route resume shortlisting requests to the Resume Shortlisting Agent.
    Use this for HR administrators to:
    - Shortlist candidates for job openings
    - Analyze resumes from spreadsheets/CSVs
    - Rank candidates based on job requirements
    - Filter candidates by skills, experience, or qualifications
    
    Example query: "Shortlist candidates for Full Stack Developer role. 
    Spreadsheet: data/resumes.csv"
    
    Args:
        query: The shortlisting request with job role and data source
        
    Returns:
        Response from the Resume Shortlisting Agent
    """
    logger.info(f"Routing to Resume Shortlisting Agent: {query[:100]}...")
    return _call_worker_agent(RESUME_SHORTLIST_URL, query)


@tool
def route_to_attendance(query: str) -> str:
    """
    Route attendance-related queries to the Attendance Automation Agent.
    Use this for:
    - Checking attendance records
    - Managing time-off requests
    - Generating attendance reports
    - Handling clock-in/clock-out automation
    - Leave balance inquiries
    - Overtime tracking
    
    Args:
        query: The attendance-related request
        
    Returns:
        Response from the Attendance Agent
    """
    logger.info(f"Routing to Attendance Agent: {query[:100]}...")
    return _call_worker_agent(ATTENDANCE_AGENT_URL, query)


@tool
def list_available_agents() -> str:
    """
    List all available worker agents and their capabilities.
    Use this when:
    - The user wants to know what services are available
    - You need to explain what the HR Automation system can do
    - The user's request is unclear and you need to guide them
    
    Returns:
        A summary of all available HR agents and their capabilities
    """
    return """
**Available HR Automation Agents:**

1. **HR Helpdesk Agent** (for Employees)
   - Answer HR policy questions (leave, benefits, remote work, expenses)
   - Provide FAQ answers (password reset, payroll, vacation balance, org chart)
   - Escalate issues to human HR representatives
   - Check ticket status

2. **Onboarding Agent** (for HR Administrators)
   - Onboard new employees
   - Set up accounts, departments, and managers
   - Configure start dates and work locations

3. **Resume Shortlisting Agent** (for HR Administrators)
   - Analyze resumes from spreadsheets/CSVs
   - Shortlist candidates for job openings
   - Rank candidates based on requirements

4. **Attendance Automation Agent** (for All)
   - Check attendance records
   - Manage time-off requests
   - Generate attendance reports
   - Track overtime and leave balances

**How to use:** Simply describe what you need, and I'll route your request to the appropriate agent.
"""


@tool
def check_agent_health(agent_name: str) -> str:
    """
    Check the health status of a specific worker agent.
    Use this to verify if an agent is online and responding.
    
    Args:
        agent_name: Name of the agent to check. 
                    Options: "helpdesk", "onboarding", "resume", "attendance"
                    
    Returns:
        Health status of the specified agent
    """
    agent_urls = {
        "helpdesk": HR_HELPDESK_URL,
        "onboarding": ONBOARDING_AGENT_URL,
        "resume": RESUME_SHORTLIST_URL,
        "attendance": ATTENDANCE_AGENT_URL
    }
    
    if agent_name.lower() not in agent_urls:
        return f"Unknown agent: {agent_name}. Available options: helpdesk, onboarding, resume, attendance"
    
    url = agent_urls[agent_name.lower()]
    health_endpoint = f"{url}/health"
    
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(health_endpoint)
            if response.status_code == 200:
                return f"✅ {agent_name.title()} Agent is healthy and responding at {url}"
            else:
                return f"⚠️ {agent_name.title()} Agent returned status {response.status_code}"
    except Exception as e:
        return f"❌ {agent_name.title()} Agent is not responding at {url}. Error: {str(e)}"
