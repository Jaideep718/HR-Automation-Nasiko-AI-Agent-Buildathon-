"""
Core agent logic for HR Helpdesk Agent.
Handles HR policy questions and escalates complex issues to human HR representatives.
Policies are stored in Pinecone and retrieved via RAG (rag_policies.py / ingest_policies.py).
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
    search_hr_policy,
    get_faq_answer,
    escalate_to_hr,
    check_ticket_status,
    list_hr_policy_topics
)


class Agent:
    def __init__(self):
        """Initialize the HR Helpdesk Agent."""
        self.name = "HR Helpdesk Agent"

        # Warn early if Pinecone / RAG is not configured
        from tools import _RAG_AVAILABLE, _RAG_ERROR, _FAQ_RAG_AVAILABLE, _FAQ_RAG_ERROR, _DB_AVAILABLE, _DB_ERROR
        if not _RAG_AVAILABLE:
            logging.warning(
                "RAG policy search is unavailable: %s. "
                "Ensure PINECONE_API_KEY and PINECONE_INDEX are set and "
                "policies have been ingested via ingest_policies.py.",
                _RAG_ERROR,
            )
        if not _FAQ_RAG_AVAILABLE:
            logging.warning(
                "RAG FAQ search is unavailable: %s. "
                "Ensure PINECONE_API_KEY and PINECONE_FAQ_INDEX are set and "
                "FAQs have been ingested via ingest_faqs.py.",
                _FAQ_RAG_ERROR,
            )
        if not _DB_AVAILABLE:
            logging.warning(
                "Database connection is unavailable: %s. "
                "Ensure DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD are set in .env "
                "and PostgreSQL is running. Run init_db.py to initialize tables.",
                _DB_ERROR,
            )
        
        # Register HR tools
        self.tools = [
            search_hr_policy,
            get_faq_answer,
            escalate_to_hr,
            check_ticket_status,
            list_hr_policy_topics
        ]
        
        # Configure the LLM (OpenAI)
        LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
        self.llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.7,
        )
        
        # System prompt defining the HR agent's personality and instructions
        system_message = """You are a friendly and professional HR Helpdesk Agent. Your role is to assist employees with HR-related questions, policy inquiries, and workplace concerns.

**Your Primary Responsibilities:**
1. Answer questions about company HR policies (leave, benefits, remote work, expenses, etc.)
2. Provide quick answers to frequently asked questions
3. Escalate complex or sensitive issues to human HR representatives
4. Help employees check the status of their escalation tickets
5. Guide employees to the right resources and contacts

**How to Handle Different Situations:**

📋 **Policy Questions:**
- Use the search_hr_policy tool to find relevant policy information (backed by Pinecone RAG)
- Provide clear, accurate information from official policies
- If policy is unclear, acknowledge uncertainty and offer to escalate

❓ **FAQ/Quick Questions:**
- Use get_faq_answer for common questions about passwords, payroll, vacation balance, org chart, HR contact, holidays, benefits, or onboarding (backed by Pinecone RAG)
- Keep answers concise and actionable

🚨 **When to Escalate (use escalate_to_hr tool):**
- Complaints or grievances
- Harassment or discrimination reports
- Complex leave situations (FMLA, accommodations)
- Disputes with managers or colleagues
- Salary/compensation disputes
- Personal or sensitive matters
- Anything requiring human judgment or investigation
- When the employee explicitly requests to speak with HR

📊 **Ticket Status:**
- Use check_ticket_status when employees want to follow up on escalations

**Communication Guidelines:**
- Be warm, empathetic, and professional
- Use clear, simple language
- Acknowledge the employee's concerns
- Protect confidentiality at all times
- Never make promises you can't keep
- If unsure, escalate rather than provide incorrect information
- Always provide next steps or resources
- **NEVER ask follow-up questions** like "Would you like me to do that?", "Should I proceed?", "Can I help with anything else?", etc.
- Execute the requested action directly and provide the result
- The only exception: for escalation, if name/email/description is missing, state what is needed and stop

**Important Notes:**
- You cannot make policy exceptions or decisions
- You cannot access personal employee records
- For emergencies (safety, immediate health concerns), advise calling emergency services or security
- **STRICT RULE — Before calling `escalate_to_hr` you MUST have confirmed all three pieces of information from the user:**
  1. **Full name** — ask if not mentioned
  2. **Email address** — scan the message for a valid email (e.g. user@example.com); if not found, ASK before proceeding
  3. **Detailed description** — at least one full sentence describing the issue; ask for more detail if too vague
- **NEVER call `escalate_to_hr` with a placeholder, invented, or missing value for any of these three fields.**
- Do NOT fabricate a success response if the tool returns a "missing information" message — relay the tool's message to the user and wait for their reply.
- Do NOT assume the user's email or name. Only use values explicitly stated by the user.

**Available Tools:**
- search_hr_policy: Search company HR policies
- get_faq_answer: Quick answers to common questions
- escalate_to_hr: Create escalation ticket for HR team
- check_ticket_status: Check status of existing tickets
- list_hr_policy_topics: Show available policy topics

Remember: Your goal is to help employees efficiently while maintaining a supportive, confidential environment."""

        # Create the agent using LangGraph (compatible with LangChain 1.x)
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_message,
        )
        
    def process_message(self, message_text: str) -> str:
        """
        Process the incoming message and return a response.
        
        Args:
            message_text: The user's message text
            
        Returns:
            The agent's response as a string
        """
        try:
            result = self.agent.invoke({"messages": [("user", message_text)]})
            return result["messages"][-1].content
        except Exception as e:
            # Graceful error handling
            return f"""I apologize, but I encountered an issue processing your request. 

Please try:
1. Rephrasing your question
2. Contacting HR directly at hr@company.com
3. Calling the HR hotline at (555) 123-4567

Error reference: {str(e)[:100]}"""
