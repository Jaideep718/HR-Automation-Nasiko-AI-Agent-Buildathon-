"""
Core agent logic for the Employee Onboarding Agent.
Automates the transition of a hired candidate into a fully onboarded employee.
"""
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tools import (
    create_employee_profile,
    send_welcome_email,
    request_documents,
    track_documents,
    update_document_status,
    schedule_orientation,
    notify_hr,
    get_onboarding_status,
)

SYSTEM_PROMPT = """You are an Employee Onboarding Agent. You automate the onboarding process for new hires.

When onboarding one or more new hires, follow this exact pipeline for EACH employee:
  1. create_employee_profile
  2. send_welcome_email
  3. request_documents
  4. notify_hr

For batch onboarding (multiple employees in one message):
- Complete all 4 steps for employee 1, then move to employee 2, and so on.
- Each employee gets their own unique employee_id from create_employee_profile — use that id for all subsequent steps for that person.
- Do NOT reuse employee IDs across employees.

IMPORTANT: Do NOT call schedule_orientation during initial onboarding.
Orientation is automatically scheduled after the employee uploads all 4 required documents.

Other tasks you can handle:
- track_documents: Check document upload progress for an employee
- update_document_status: Mark a specific document as uploaded or pending
- get_onboarding_status: Full summary of an employee's onboarding (profile, docs, schedule, messages)
- schedule_orientation: Only call this if explicitly asked AND all documents are uploaded

Always use the employee_id returned by create_employee_profile (e.g. EMP-1001) for all subsequent tool calls for that employee.
Be concise and confirm each completed step.

CRITICAL: NEVER ask the user for more information or clarification. There is no multi-turn conversation.
All required data MUST be in the original message. If a field is missing, use a reasonable default or skip that step.
Do NOT ask follow-up questions under any circumstances."""


class Agent:
    def __init__(self):
        self.tools = [
            create_employee_profile,
            send_welcome_email,
            request_documents,
            track_documents,
            update_document_status,
            schedule_orientation,
            notify_hr,
            get_onboarding_status,
        ]

        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.memory = MemorySaver()

        self.agent = create_react_agent(
            self.llm, self.tools, prompt=SYSTEM_PROMPT, checkpointer=self.memory
        )

    def process_message(self, message_text: str, session_id: str = "default") -> str:
        """Process incoming messages with conversation memory per session."""
        config = {"configurable": {"thread_id": session_id}}
        result = self.agent.invoke({"messages": [("user", message_text)]}, config)
        return result["messages"][-1].content
