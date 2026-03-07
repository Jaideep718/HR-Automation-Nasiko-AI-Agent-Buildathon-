from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.agents import AgentExecutor, create_tool_calling_agent
from dotenv import load_dotenv

load_dotenv()

from tools import (
    view_leave_requests,
    approve_leave,
    approve_leave_by_number,
    reject_leave,
    reject_leave_by_number,
    track_working_days,
    track_working_days_by_email,       # ✅ email-based fallback
    monitor_absenteeism,
    monitor_absenteeism_by_email,      # ✅ email-based fallback
    get_attendance_report,
    detect_absenteeism,
    hr_summary,
)


class Agent:

    def __init__(self):

        self.name = "HR Attendance Automation Agent"

        self.tools = [
            view_leave_requests,
            approve_leave,
            approve_leave_by_number,
            reject_leave,
            reject_leave_by_number,
            track_working_days,
            track_working_days_by_email,
            monitor_absenteeism,
            monitor_absenteeism_by_email,
            get_attendance_report,
            detect_absenteeism,
            hr_summary,
        ]

        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1,
            timeout=30,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an HR Attendance Automation Assistant helping HR managers.

Your responsibilities include:
1. Viewing pending leave requests
2. Approving leave requests
3. Rejecting leave requests
4. Sending email notifications (handled automatically by the tools)
5. Tracking employee working days
6. Monitoring absenteeism
7. Generating attendance reports
8. Detecting poor attendance
9. Providing HR summary dashboards

Rules:
- Always use tools when performing HR operations.
- Never fabricate employee information.
- Employee primary key is their EMAIL — always use email to uniquely identify an employee.

Handling duplicate names (leave requests):
- If multiple employees share the same name in leave requests, ask HR to run
  'view leave requests' first to see the numbered list, then use
  approve_leave_by_number or reject_leave_by_number with the correct number.

Handling duplicate names (attendance / absenteeism):
- If track_working_days or monitor_absenteeism returns multiple employees
  with the same name, show the disambiguation list (which includes each employee's email).
- Ask HR to confirm which email belongs to the employee they mean.
- Then use track_working_days_by_email or monitor_absenteeism_by_email
  with the confirmed email.

General:
- If HR provides a reason when rejecting a leave request, pass the reason to the rejection tool.
- HR may refer to previous results using phrases like "first", "second", or "that request".
- Always report back whether email notifications were sent successfully.
"""),

            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self.llm, self.tools, prompt)

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
        )

        self._session_store: dict[str, BaseChatMessageHistory] = {}

        self.agent_with_history = RunnableWithMessageHistory(
            self.agent_executor,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def _get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """Return (or create) the message history for a given session."""
        if session_id not in self._session_store:
            self._session_store[session_id] = ChatMessageHistory()
        return self._session_store[session_id]

    def process_message(self, message_text: str, session_id: str = "default") -> str:
        """
        Process an HR message and return the agent's response.

        Args:
            message_text: The HR manager's message.
            session_id:   Conversation session identifier. Use different
                          session IDs to maintain separate conversations.
        """
        result = self.agent_with_history.invoke(
            {"input": message_text},
            config={"configurable": {"session_id": session_id}},
        )
        return result["output"]