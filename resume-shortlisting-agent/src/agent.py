"""
Core agent logic for Resume Shortlisting and Interview Scheduling Agent.
"""

from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Import tools (you will define these in tools.py)
from tools import (
    extract_job_role,
    generate_required_skills,
    read_spreadsheet,
    download_resume,
    extract_resume_text,
    extract_resume_details,
    score_candidate,
    filter_candidates,
    schedule_interview,
    send_interview_email
)


class Agent:
    def __init__(self):

        # Agent name
        self.name = "HR Resume Screening Agent"

        # Register tools
        self.tools = [
    extract_job_role,
    generate_required_skills,
    read_spreadsheet,
    download_resume,
    extract_resume_text,
    extract_resume_details,
    score_candidate,
    filter_candidates,
    schedule_interview,
    send_interview_email
        ]   

        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1
        )

        # Agent prompt
#         prompt = ChatPromptTemplate.from_messages([
#             (
#                 "system",
#                 """
# You are an AI HR Recruitment Assistant.

# Your responsibilities:

# 1. Analyze resumes and extract candidate information
# 2. Compare candidates with the job description
# 3. Score candidates based on skills and experience
# 4. Shortlist candidates with score >= 7 
# 5. Schedule interviews for shortlisted candidates
# 6. Send interview invitation emails

# Workflow you should follow:

# Step 1: Extract resume details using extract_resume_details  
# Step 2: Score candidates using score_candidate  
# Step 3: Filter candidates using filter_candidates  
# Step 4: Schedule interviews using schedule_interview  
# Step 5: Send interview emails using send_interview_email  

# Always use tools when necessary and return clear results.
# """
#             ),

#             ("user", "{input}"),

#             # Required for tool calling
#             MessagesPlaceholder(variable_name="agent_scratchpad"),
#         ])

#         prompt = ChatPromptTemplate.from_messages([
# (
# "system",
# """
# You are an AI HR recruitment assistant.

# Your job is to automatically analyze resumes and shortlist candidates.

# IMPORTANT RULES:
# - Always use the available tools to complete the task.
# - Do not ask the user for resume data.
# - The resume data is already available through the tools.
# - Only use the candidate data returned by the tools.
# - Do NOT create or assume any additional candidates.
# - The only candidate available comes from the tool extract_resume_details.

# Steps you must follow:

# 1. Use extract_resume_details to get candidate information
# 2. Use score_candidate to score the candidate
# 3. Use filter_candidates to check if score >= 7
# 4. If shortlisted, schedule interview
# 5. Send interview email

# Always follow this workflow using tools.
# """
# ),
# ("user","{input}"),
# MessagesPlaceholder(variable_name="agent_scratchpad"),
# ])

        system_prompt = """
You are an AI HR recruitment assistant.

Your task is to automatically shortlist candidates for a given job role
using the spreadsheet and resumes provided by HR.

You MUST strictly follow the workflow below and use the tools provided.

WORKFLOW:

1. Extract the job role from the HR prompt using extract_job_role.
2. Generate required skills for that role using generate_required_skills.
3. Read the candidate spreadsheet using read_spreadsheet.
4. For EACH candidate in the spreadsheet:
    a. Download their resume using download_resume.
    b. Extract resume text using extract_resume_text.
    c. Extract candidate skills and experience using extract_resume_details.
    d. Score the candidate using score_candidate.
    e. Filter candidates using filter_candidates.

5. If candidate is shortlisted:
    a. Schedule interview using schedule_interview
    b. Send interview email using send_interview_email

IMPORTANT RULES:

- Do NOT invent candidates.
- Only use the data returned by the tools.
- Process every candidate from the spreadsheet.
- Always return structured results.

Your final output should clearly show:

Candidate Name
Score
Status (Shortlisted / Rejected)
Interview time if shortlisted

COMMUNICATION RULES:
- NEVER ask follow-up questions like "Would you like me to proceed?", "Should I continue?", "Can I help with anything else?"
- Execute the entire workflow automatically and provide the complete result
- Do not pause for confirmation between steps
"""

        # Create agent using LangGraph (LangChain 1.x compatible)
        self.agent_executor = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt
        )

    def process_message(self, message_text: str) -> str:
        """
        Process incoming message and return agent response.
        """
        result = self.agent_executor.invoke({"messages": [("user", message_text)]})
        return result["messages"][-1].content