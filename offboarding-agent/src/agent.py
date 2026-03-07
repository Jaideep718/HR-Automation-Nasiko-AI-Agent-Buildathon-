"""
Core agent logic for the Employee Offboarding Agent.
Automates the full offboarding lifecycle from resignation to final exit.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tools import (
    initiate_offboarding,
    send_exit_notification,
    track_assets,
    update_asset_status,
    schedule_exit_interview,
    revoke_access,
    assign_knowledge_transfer,
    notify_hr_final_settlement,
    get_offboarding_status,
)

SYSTEM_PROMPT = """You are an Employee Offboarding Agent. You automate the offboarding process for departing employees.

When offboarding an employee, follow this exact pipeline:
  1. initiate_offboarding — register the resignation and calculate notice period
  2. send_exit_notification — email the employee their offboarding timeline and checklist
  3. notify_hr_final_settlement — alert HR to begin final settlement processing

Other tasks you can handle on request:
  - track_assets: Check which company assets have been returned
  - update_asset_status: Mark a specific asset as returned or lost
  - schedule_exit_interview: Schedule a confidential exit interview
  - revoke_access: Flag all system access for revocation and notify IT/HR
  - assign_knowledge_transfer: Assign a handover to a successor
  - get_offboarding_status: Full summary of an offboarding case

CRITICAL RULES:
- NEVER ask the user for more information. All required data MUST be in the original message.
  If any field is missing, use reasonable defaults (level="mid", reason="not specified").
- Always use the offboarding_id returned by initiate_offboarding for all subsequent tool calls.
- Be concise. Confirm each completed step briefly.
- Do NOT invent data that was not provided. Only use defaults for optional fields."""


class Agent:
    def __init__(self):
        self.tools = [
            initiate_offboarding,
            send_exit_notification,
            track_assets,
            update_asset_status,
            schedule_exit_interview,
            revoke_access,
            assign_knowledge_transfer,
            notify_hr_final_settlement,
            get_offboarding_status,
        ]

        LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
        HF_TOKEN = os.getenv("HF_TOKEN")
        HF_BASE_URL = os.getenv("HF_BASE_URL", "https://api-inference.huggingface.co/v1")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

        if HF_TOKEN:
            self.llm = ChatOpenAI(
                model=LLM_MODEL, api_key=HF_TOKEN, base_url=HF_BASE_URL, temperature=0
            )
        else:
            self.llm = ChatOpenAI(
                model=LLM_MODEL, api_key=OPENAI_API_KEY, temperature=0
            )

        self.memory = MemorySaver()
        self.agent = create_react_agent(
            self.llm, self.tools, prompt=SYSTEM_PROMPT, checkpointer=self.memory
        )

    def process_message(self, message_text: str, session_id: str = "default") -> str:
        config = {"configurable": {"thread_id": session_id}}
        result = self.agent.invoke({"messages": [("user", message_text)]}, config)
        return result["messages"][-1].content
