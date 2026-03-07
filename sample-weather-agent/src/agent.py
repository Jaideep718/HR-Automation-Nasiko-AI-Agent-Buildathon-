"""
Core agent logic for Weather Assistant.
"""
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent

from tools import get_weather, get_weather_forecast, convert_temperature

class Agent:
    def __init__(self):
        # Initialize your weather assistant agent
        self.name = "Weather Assistant Agent"
        
        # Define Tools - import the weather-related tools
        self.tools = [get_weather, get_weather_forecast, convert_temperature]
        
        # Initialize LangChain components
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        
        # Enhanced prompt for weather assistant
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a friendly and helpful weather assistant agent. Your role is to:
            
            1. Help users get current weather information for cities
            2. Provide weather forecasts for multiple days
            3. Convert temperatures between different units (Celsius, Fahrenheit, Kelvin)
            4. Give weather-related advice and recommendations
            
            Always be conversational and helpful. When users ask about weather, use the appropriate tools to get accurate information.
            If users ask for cities not in your database, let them know which cities you support.
            
            Available tools:
            - get_weather: Get current weather for a city
            - get_weather_forecast: Get multi-day weather forecast
            - convert_temperature: Convert between C, F, and K units
            
            Be concise but friendly in your responses."""),
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
