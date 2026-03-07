import logging
import uuid
import uvicorn
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from agent import Agent
from models import JsonRpcRequest, JsonRpcResponse, Task, TaskStatus, Artifact, ArtifactPart

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-template")

app = FastAPI()

# Initialize the agent
agent = Agent()


@app.post("/")
async def handle_rpc(request: JsonRpcRequest):
    """Handle JSON-RPC requests from HR or Nasiko platform."""

    if request.method == "message/send":

        try:
            user_message = request.params.message
            session_id = request.params.session_id

            # Extract user text
            input_text = ""

            for part in user_message.parts:
                if part.kind == "text" and part.text:
                    input_text += part.text

            logger.info(f"Received message: {input_text[:50]}")

            # Run agent
            response_text = agent.process_message(input_text)

            task_id = str(uuid.uuid4())
            context_id = session_id if session_id else str(uuid.uuid4())

            artifact = Artifact(
                parts=[ArtifactPart(text=response_text)]
            )

            task = Task(
                id=task_id,
                status=TaskStatus(
                    state="completed",
                    timestamp=datetime.now().isoformat()
                ),
                artifacts=[artifact],
                contextId=context_id
            )

            return JsonRpcResponse(
                id=request.id,
                result=task
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    else:
        raise HTTPException(status_code=404, detail="Method not supported")


if __name__ == "__main__":

    import click

    @click.command()
    @click.option('--host', default='0.0.0.0')
    @click.option('--port', default=5000)
    def main(host: str, port: int):
        uvicorn.run(app, host=host, port=port)

    main()