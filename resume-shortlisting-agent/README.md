# Weather Assistant Agent

This is a sample weather assistant agent built using the [A2A (Agent-to-Agent)](https://github.com/ashishsharma/nasiko) template.

It provides weather information, forecasts, and temperature conversions for major cities through a conversational interface.

## Features

- **Current Weather**: Get real-time weather information for supported cities
- **Weather Forecast**: Multi-day weather forecasting (up to 7 days)  
- **Temperature Conversion**: Convert between Celsius, Fahrenheit, and Kelvin
- **Conversational Interface**: Natural language interaction powered by LangChain

## Supported Cities

- London
- New York  
- Tokyo
- Paris
- Mumbai

## Frameworks
- **Server**: FastAPI
- **Agent Logic**: LangChain with OpenAI GPT-4
- **Protocol**: A2A JSON-RPC 2.0

## Structure

- `src/__main__.py`: FastAPI server handling A2A JSON-RPC `message/send` requests
- `src/models.py`: A2A protocol Pydantic models (Message, Task, etc.)
- `src/tools.py`: Weather-specific tools (get_weather, get_weather_forecast, convert_temperature)
- `src/agent.py`: Weather assistant agent logic and prompt configuration
- `AgentCard.json`: Agent metadata and capabilities
- `Dockerfile`: Docker configuration

## How to Run

1. **Set OpenAI API Key**:
   ```bash
   export OPENAI_API_KEY=your_openai_api_key
   ```

2. **Build and Run with Docker**:
   ```bash
   docker build -t weather-agent .
   docker run -p 5000:5000 -e OPENAI_API_KEY=$OPENAI_API_KEY weather-agent
   ```

3. **Test the Agent**:
   ```bash
   curl -X POST http://localhost:5000/ \
   -H "Content-Type: application/json" \
   -d '{
     "jsonrpc": "2.0",
     "id": "1",
     "method": "message/send", 
     "params": {
       "message": {
         "role": "user",
         "parts": [{"kind": "text", "text": "What is the weather like in London?"}]
       }
     }
   }'
   ```

## Example Interactions

- "What's the weather like in Tokyo?"
- "Give me a 5-day forecast for New York"
- "Convert 25 degrees Celsius to Fahrenheit"
- "Is it raining in London today?"

## Customization

To modify this agent for your own use case:

1. **Edit `src/tools.py`**: Add your own tools using the `@tool` decorator
2. **Edit `src/agent.py`**: Customize the system prompt and agent behavior  
3. **Update `AgentCard.json`**: Modify agent metadata and capabilities
4. **Update Dockerfile**: Add any additional dependencies

