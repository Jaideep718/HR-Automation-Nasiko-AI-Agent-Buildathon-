"""
Core agent logic.
"""
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent

from tools import example_tool

class Agent:
    def __init__(self):
        # Initialize your agent
        self.name = "FastAPI Agent"
        
        # Define Tools
        self.tools = [example_tool]
        
        # Initialize LangChain components
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant."),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
        
    def process_message(self, message_text: str) -> str:
        """
        Process the incoming message using LangChain.
        """
        result = self.agent_executor.invoke({"input": message_text})
        return result["output"]
