# Hackathon Agent Development Guide

Complete guide for building and deploying agents using the Nasiko platform.

## Table of Contents

1. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Understanding the A2A Protocol](#understanding-the-a2a-protocol)
2. [Building Your Agent](#building-your-agent)
   - [Step 1: Copy the Template](#step-1-copy-the-template)
   - [Step 2: Define Your Tools](#step-2-define-your-tools)
   - [Step 3: Configure Your Agent](#step-3-configure-your-agent)
   - [Step 4: Update Agent Metadata (Optional)](#step-4-update-agent-metadata-optional)
   - [Step 5: Create docker-compose.yml (Required)](#step-5-create-docker-composeyml-required)
3. [Testing Your Agent](#testing-your-agent)
   - [Local Testing](#local-testing)
   - [Testing Different Scenarios](#testing-different-scenarios)
4. [Deployment Methods](#deployment-methods)
   - [Connect GitHub](#connect-github)
   - [Upload ZIP File](#upload-zip-file)
5. [Agent Card Format](#agent-card-format)
   - [Field Descriptions](#field-descriptions)
   - [AgentCard Validation](#agentcard-validation)
6. [Common Issues & Troubleshooting](#common-issues--troubleshooting)
   - [Build Issues](#build-issues)
   - [Runtime Issues](#runtime-issues)
   - [Deployment Issues](#deployment-issues)
   - [Testing Issues](#testing-issues)
7. [Best Practices](#best-practices)
   - [Code Organization](#code-organization)
   - [Agent Design](#agent-design)
   - [Performance](#performance)
   - [Security](#security)
   - [Testing Strategy](#testing-strategy)
   - [Documentation](#documentation)
8. [Sample Agent Examples](#sample-agent-examples)
9. [Support and Resources](#support-and-resources)

---

## Getting Started

### Prerequisites

- Python 3.12
- Docker Desktop installed
- OpenAI API Key (for LangChain agents)
- Git (for GitHub deployment method)
- Code editor of your choice

### Understanding the A2A Protocol

The Agent-to-Agent (A2A) protocol is a JSON-RPC 2.0 based system that allows agents to communicate with each other and with the Nasiko platform. Your agent will:

1. Receive messages via HTTP POST requests
2. Process them using your custom logic 
3. Return structured responses in A2A format

---

## Building Your Agent

### Step 1: Copy the Template

```bash
# Copy the agent template
cp -r agent-template my-awesome-agent
cd my-awesome-agent
```

### Step 2: Define Your Tools

Edit `src/tools.py` to define your agent's capabilities using LangChain's `@tool` decorator:

```python
from langchain_core.tools import tool

@tool
def my_custom_tool(param1: str, param2: int) -> str:
    """
    Description of what this tool does.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2
    """
    # Your tool logic here
    return f"Result: {param1} with {param2}"

@tool  
def another_tool(query: str) -> str:
    """
    Another tool that processes queries.
    
    Args:
        query: The query to process
    """
    # Tool implementation
    return f"Processed: {query}"
```

**Tool Guidelines:**
- Use clear, descriptive function names
- Provide detailed docstrings (the LLM uses these to understand when to call your tools)
- Handle errors gracefully with try/catch blocks
- Return strings (the A2A protocol expects text responses)
- Keep tools focused on single responsibilities

### Step 3: Configure Your Agent

Edit `src/agent.py` to customize your agent's behavior:

```python
"""
Core agent logic for My Awesome Agent.
"""
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent

# Import your tools
from tools import my_custom_tool, another_tool

class Agent:
    def __init__(self):
        # Initialize your agent
        self.name = "My Awesome Agent"
        
        # Register your tools
        self.tools = [my_custom_tool, another_tool]
        
        # Configure the LLM
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        
        # Define your agent's personality and instructions
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert assistant specialized in [YOUR DOMAIN].
            
            Your role is to:
            1. [Primary function]
            2. [Secondary function]  
            3. [Additional capabilities]
            
            Always be helpful and accurate. Use the available tools to provide
            the best possible assistance to users.
            
            Available tools:
            - my_custom_tool: [Brief description]
            - another_tool: [Brief description]"""),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create the agent
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
        
    def process_message(self, message_text: str) -> str:
        """Process incoming messages."""
        result = self.agent_executor.invoke({"input": message_text})
        return result["output"]
```

**Agent Configuration Tips:**
- Write clear system prompts that explain the agent's role
- Set appropriate temperature (0.1 for deterministic, 0.7 for creative)
- List available tools in the system prompt to help the LLM understand capabilities
- Test different prompt variations to optimize performance

### Step 4: Update Agent Metadata (Optional)

**Note**: The `AgentCard.json` file is optional. If not provided, a backend agent will automatically generate one during the upload and deployment process.

If you want to customize your agent metadata, you can create/edit `AgentCard.json`:

```json
{
    "protocolVersion": "0.2.9",
    "name": "My Awesome Agent",
    "description": "A detailed description of what your agent does and its capabilities.",
    "url": "http://localhost:5000/",
    "preferredTransport": "JSONRPC",
    "provider": {
        "organization": "Your Team Name",
        "url": "https://github.com/your-username/your-agent-repo"
    },
    "iconUrl": "http://localhost:5000/icon.png",
    "version": "1.0.0",
    "documentationUrl": "http://localhost:5000/docs",
    "capabilities": {
        "streaming": false,
        "pushNotifications": false,
        "stateTransitionHistory": true,
        "chat_agent": true
    },
    "securitySchemes": {},
    "security": [],
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [
        {
            "name": "skill_name",
            "description": "Description of what this skill does"
        }
    ],
    "supportsAuthenticatedExtendedCard": false,
    "signatures": []
}
```

**Important Notes:**
- The `skills` array should reflect your actual tools
- Update the `provider.url` to your GitHub repository
- The `url` field will be updated during deployment
- Version should follow semantic versioning (1.0.0, 1.1.0, etc.)

### Step 5: Create docker-compose.yml (Required)

**Important**: The `docker-compose.yml` file is required for deployment validation to pass.

Create a `docker-compose.yml` file in your agent root directory:

```yaml
services:
  your-agent-name:
    build: .
    container_name: your-agent-name
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      # Add other environment variables as needed
    stdin_open: true
    ports:
      - "5000"
    tty: true
    networks:
      - agents-net

networks:
  agents-net:
    external: true
```

**Key Requirements:**
- Service name should match your agent name
- Port `5000` must be exposed (matches Dockerfile)
- Include all required environment variables
- Use the `agents-net` external network

---

## Testing Your Agent

### Local Testing

1. **Build the Docker container:**
   ```bash
   docker build -t my-awesome-agent .
   ```

2. **Run the agent:**
   ```bash
   export OPENAI_API_KEY=your_openai_api_key_here
   docker run -p 5000:5000 -e OPENAI_API_KEY=$OPENAI_API_KEY my-awesome-agent
   ```

3. **Test with curl:**
   ```bash
   curl -X POST http://localhost:5000/ \
   -H "Content-Type: application/json" \
   -d '{
     "jsonrpc": "2.0",
     "id": "test-1",
     "method": "message/send",
     "params": {
       "message": {
         "role": "user", 
         "parts": [{"kind": "text", "text": "Hello, can you help me?"}]
       }
     }
   }'
   ```

4. **Expected response format:**
   ```json
   {
     "jsonrpc": "2.0",
     "id": "test-1", 
     "result": {
       "id": "unique-task-id",
       "kind": "task",
       "status": {
         "state": "completed",
         "timestamp": "2024-01-01T12:00:00"
       },
       "artifacts": [
         {
           "id": "artifact-id",
           "kind": "text",
           "parts": [
             {
               "kind": "text",
               "text": "Agent response here"
             }
           ]
         }
       ]
     }
   }
   ```

### Testing Different Scenarios

Test your agent with various inputs:

```bash
# Test tool calling
curl -X POST http://localhost:5000/ \
-H "Content-Type: application/json" \
-d '{
  "jsonrpc": "2.0",
  "id": "test-2",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Use your custom tool to process data XYZ"}]
    }
  }
}'

# Test error handling
curl -X POST http://localhost:5000/ \
-H "Content-Type: application/json" \
-d '{
  "jsonrpc": "2.0", 
  "id": "test-3",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Do something impossible"}]
    }
  }
}'
```

---

## Deployment Methods

### Connect GitHub

This is the recommended method for hackathon submissions as it provides version control and easy updates.

#### Step 1: Create GitHub Repository

1. Create a new repository on GitHub
2. Initialize it with a README
3. Clone it locally:
   ```bash
   git clone https://github.com/your-username/my-awesome-agent.git
   cd my-awesome-agent
   ```

#### Step 2: Prepare Your Code

1. Copy your agent files to the repository:
   ```bash
   cp -r /path/to/your/agent/* .
   ```

2. Create/update `.gitignore`:
   ```gitignore
   __pycache__/
   *.pyc
   *.pyo
   *.pyd
   .Python
   env/
   venv/
   .env
   .vscode/
   .DS_Store
   ```

3. Ensure your `Dockerfile` is properly configured:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY src/ /app

   RUN pip install --no-cache-dir \
     fastapi>=0.109.0 \
     uvicorn>=0.27.0 \
     pydantic>=2.6.0 \
     python-dotenv>=1.0.0 \
     requests>=2.31.0 \
     "langchain>=0.2.0,<0.3.0" \
     "langchain-openai>=0.1.0,<0.2.0" \
     click>=8.1.7

   ENV PYTHONUNBUFFERED=1

   CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "5000"]
   ```

#### Step 3: Commit and Push

```bash
git add .
git commit -m "Initial agent implementation"
git push origin main
```

#### Step 4: Deploy via Nasiko Dashboard

1. **Access the Dashboard**
   - Log into the Nasiko dashboard
   - Navigate to the "Add Agent" section

2. **Connect GitHub Repository**
   - Click on "Connect GitHub" option
   - Complete the OAuth authentication flow when prompted
   - Grant necessary permissions to access your repositories

3. **Select Repository**
   - Browse and select your agent repository from the list of available repos
   - The platform will automatically detect and deploy your agent to the Nasiko registry

4. **Deployment Complete**
   - Your agent will be built and deployed automatically
   - Monitor the deployment status in the dashboard
   - Once deployed, your agent will be available in the registry

#### Step 5: Making Updates

To update your deployed agent:

1. Make changes to your code locally
2. Test the changes:
   ```bash
   docker build -t my-agent-test .
   docker run -p 5000:5000 -e OPENAI_API_KEY=$OPENAI_API_KEY my-agent-test
   ```
3. Commit and push changes:
   ```bash
   git add .
   git commit -m "Updated feature X"  
   git push origin main
   ```
4. Navigate to the "Your Agents" section in the dashboard and click on the "Re-upload Agent" in the "Agent actions" column

---

### Upload ZIP File

This method is useful for quick prototyping or when you don't want to use GitHub.

#### Step 1: Prepare Your Agent

1. **Ensure your agent structure is correct:**
   ```
   my-awesome-agent/
   ├── src/
   │   ├── __init__.py
   │   ├── __main__.py
   │   ├── agent.py
   │   ├── tools.py
   │   └── models.py
   ├── docker-compose.yml  (Required)
   ├── Dockerfile         (Required)
   ├── AgentCard.json     (Optional - auto-generated if missing)
   └── README.md
   ```

2. **Test locally first:**
   ```bash
   cd my-awesome-agent
   docker build -t test-agent .
   docker run -p 5000:5000 -e OPENAI_API_KEY=$OPENAI_API_KEY test-agent
   # Test with curl as shown earlier
   ```

#### Step 2: Create ZIP Package

1. **Create the ZIP file:**
   ```bash
   cd /path/to/parent/directory
   zip -r my-awesome-agent.zip my-awesome-agent/ -x "*.pyc" "*/__pycache__/*" "*/.git/*"
   ```

2. **Verify ZIP contents:**
   ```bash
   unzip -l my-awesome-agent.zip
   ```

#### Step 3: Deploy via Dashboard

1. **Access the Dashboard**
   - Log into the Nasiko dashboard
   - Navigate to the "Add Agent" section

2. **Upload ZIP File**
   - Click on "Upload ZIP" option
   - Select your `my-awesome-agent.zip` file from your computer
   - Click upload to deploy

3. **Deployment Process**
   - The platform will automatically:
     - Extract and validate your ZIP file
     - Check for required files (Dockerfile, docker-compose.yml)
     - Generate AgentCard.json if not provided
     - Build the Docker container
     - Deploy the agent to the Nasiko registry

4. **Deployment Complete**
   - Monitor the deployment status in the dashboard
   - Once deployed, your agent will be available in the registry

#### Step 4: Updates via ZIP

To update an agent deployed via ZIP:

1. Make your code changes
2. Test locally
3. Create a new ZIP file with a version suffix:
   ```bash
   zip -r my-awesome-agent-v1.1.zip my-awesome-agent/
   ```
4. Navigate to the "Your Agents" section in the dashboard and click on the "Re-upload Agent" in the "Agent actions" column
5. Select the new ZIP file and click upload
6. Monitor the deployment status in the dashboard

---

## Agent Card Format

The `AgentCard.json` file is **optional** - if not provided, it will be auto-generated during deployment. However, if you want to customize your agent's metadata, here's the detailed format:

```json
{
  "protocolVersion": "0.2.9",
  "name": "Agent Display Name",
  "description": "Comprehensive description of agent capabilities and use cases",
  "url": "http://localhost:5000/",
  "preferredTransport": "JSONRPC",
  "provider": {
    "organization": "Your Organization/Team Name",
    "url": "https://github.com/your-username/agent-repo"
  },
  "iconUrl": "http://localhost:5000/icon.png",
  "version": "1.0.0",
  "documentationUrl": "http://localhost:5000/docs",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true,
    "chat_agent": true
  },
  "securitySchemes": {},
  "security": [],
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"], 
  "skills": [
    {
      "name": "skill_identifier",
      "description": "What this skill does"
    }
  ],
  "supportsAuthenticatedExtendedCard": false,
  "signatures": []
}
```

### Field Descriptions

- **protocolVersion**: Must be "0.2.9" (current A2A version)
- **name**: Human-readable agent name (displayed in UI)
- **description**: Detailed explanation of what the agent does
- **url**: Will be updated by platform during deployment
- **provider.organization**: Your team/organization name
- **provider.url**: Link to source code repository
- **version**: Semantic version of your agent
- **skills**: Array of capabilities your agent provides
- **capabilities.chat_agent**: Should be `true` for conversational agents

### AgentCard Validation

The platform validates your AgentCard.json during deployment. Common errors:

❌ **Invalid JSON syntax**
```json
{
  "name": "My Agent",  // Comments not allowed in JSON
  "description": "Description"  // Missing comma
}
```

✅ **Valid JSON**
```json
{
  "name": "My Agent",
  "description": "Description",
  "protocolVersion": "0.2.9"
}
```

❌ **Missing required fields**
```json
{
  "name": "My Agent"
  // Missing protocolVersion, description, etc.
}
```

✅ **All required fields present**
```json
{
  "protocolVersion": "0.2.9",
  "name": "My Agent",
  "description": "Complete description",
  "url": "http://localhost:5000/"
  // ... other required fields
}
```

---

## Common Issues & Troubleshooting

### Build Issues

**Problem**: Docker build fails with dependency errors
```
ERROR: Could not find a version that satisfies the requirement langchain>=0.2.0
```
**Solution**: Update your Dockerfile with specific versions:
```dockerfile
RUN pip install --no-cache-dir \
  "langchain==0.2.16" \
  "langchain-openai==0.1.23" \
  "fastapi==0.109.2"
```

**Problem**: Python module import errors
```
ModuleNotFoundError: No module named 'tools'
```
**Solution**: Ensure proper Python path setup in `__main__.py`:
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import Agent
```

### Runtime Issues

**Problem**: Agent returns 500 errors
```
{"error": "Internal Server Error", "detail": "OpenAI API key not found"}
```
**Solution**: 
- Verify `OPENAI_API_KEY` environment variable is set
- Check environment variables in deployment configuration
- Test locally with: `echo $OPENAI_API_KEY`

**Problem**: Agent doesn't call tools
```
Agent responds with text but never uses the defined tools
```
**Solution**:
- Improve tool descriptions in docstrings
- Test tool calling logic locally
- Add tools to system prompt explicitly
- Verify tools are imported correctly in `agent.py`

**Problem**: JSON-RPC format errors
```
{"error": "Invalid request", "code": -32600}
```
**Solution**: Check request format matches A2A protocol:
```bash
# Correct format
curl -X POST http://localhost:5000/ \
-H "Content-Type: application/json" \
-d '{
  "jsonrpc": "2.0",
  "id": "test-1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Your message"}]
    }
  }
}'
```

### Deployment Issues

**Problem**: Validation fails during upload
```
Validation failed: Required files missing
```
**Solution**:
- Ensure `Dockerfile` is present in root directory
- Ensure `docker-compose.yml` is present (required for validation)
- Check file structure matches expected format
- Verify ZIP file includes all necessary files

**Problem**: Build timeout during deployment
```
Build failed: Timeout after 10 minutes
```
**Solution**:
- Optimize Dockerfile to reduce build time
- Use more specific Python packages
- Remove unnecessary dependencies
- Use multi-stage builds if needed

**Problem**: Agent shows as "Crashed" status
```
Agent status: Crashed, Exit code: 1
```
**Solution**:
- Check deployment logs for error details
- Verify port configuration (5000) in both Dockerfile and docker-compose.yml
- Ensure all environment variables are set correctly
- Test Docker container locally first

### Testing Issues

**Problem**: Local testing works but deployed agent fails
```
Local: ✅ Works perfectly
Deployed: ❌ Always returns errors
```
**Solution**:
- Check environment variables in deployment
- Verify network/firewall settings
- Compare local vs deployed container logs
- Ensure all dependencies are in Dockerfile

---

## Best Practices

### Code Organization

1. **Modular Tools**: Keep each tool in a separate function with clear responsibilities
2. **Error Handling**: Always include try/catch blocks in tools
3. **Type Hints**: Use Python type hints for better code clarity
4. **Documentation**: Write clear docstrings for all tools and functions

### Agent Design

1. **Clear Purpose**: Design agents with specific, well-defined purposes
2. **Tool Composition**: Create multiple small tools rather than one complex tool
3. **Conversational Flow**: Design prompts that encourage natural conversation
4. **Fallback Handling**: Plan for scenarios where tools can't provide answers

### Performance

1. **Efficient Tools**: Optimize tool execution time
2. **Caching**: Implement caching if required for expensive operations
3. **Resource Usage**: Monitor memory and CPU usage

### Security

1. **Input Validation**: Validate all user inputs in tools
2. **API Keys**: Never hardcode API keys in source code
3. **Error Messages**: Don't expose sensitive information in error messages
4. **Dependencies**: Keep dependencies updated and secure

### Testing Strategy

1. **Unit Tests**: Test individual tools independently
2. **Integration Tests**: Test agent conversation flows
3. **Edge Cases**: Test with malformed inputs and edge cases
4. **Load Testing**: Test agent under concurrent requests

### Documentation

1. **README**: Provide clear setup and usage instructions
2. **API Documentation**: Document all tools and their parameters
3. **Examples**: Include example interactions and use cases
4. **Troubleshooting**: Document common issues and solutions

---

## Sample Agent Examples

Check out the `sample-weather-agent.zip` file for a complete example that demonstrates:

- Multiple tool definitions (`get_weather`, `get_weather_forecast`, `convert_temperature`)
- Proper agent configuration with domain-specific prompting
- Comprehensive testing examples
- Deployment-ready structure

Use this as a reference for your own agent development!

---

Good luck with your hackathon project! 🚀