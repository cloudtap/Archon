from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Dict, List
import requests
import asyncio
import uuid
import os

from utils.utils import write_to_log

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server with ERROR logging level
mcp = FastMCP("archon", log_level="ERROR")

# Store active threads
active_threads: Dict[str, List[str]] = {}

# FastAPI service URL
GRAPH_SERVICE_URL = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8100")

@mcp.tool()
async def create_thread() -> str:
    """Create a new conversation thread for Archon.
    Always call this tool before invoking Archon for the first time in a conversation.
    (if you don't already have a thread ID)
    
    Returns:
        str: A unique thread ID for the conversation
    """
    thread_id = str(uuid.uuid4())
    active_threads[thread_id] = []
    write_to_log(f"Created new thread: {thread_id}")
    return thread_id


def _make_request(thread_id: str, user_input: str, config: dict) -> str:
    """Make synchronous request to graph service"""
    try:
        response = requests.post(
            f"{GRAPH_SERVICE_URL}/invoke",
            json={
                "message": user_input,
                "thread_id": thread_id,
                "is_first_message": not active_threads[thread_id],
                "config": config
            },
            timeout=300  # 5 minute timeout for long-running operations
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        write_to_log(f"Request timed out for thread {thread_id}")
        raise TimeoutError("Request to graph service timed out. The operation took longer than expected.")
    except requests.exceptions.RequestException as e:
        write_to_log(f"Request failed for thread {thread_id}: {str(e)}")
        raise


@mcp.tool()
async def run_agent(thread_id: str, user_input: str) -> str:
    """
    Processes a user input within an existing conversation thread and returns the agent's response.
    
    Validates the thread ID, sends the user input to the external graph service, appends the input to the thread's history, and returns the generated response. Raises a ValueError if the thread ID does not exist.
    
    Args:
        thread_id: Unique identifier for the conversation thread.
        user_input: The user's message to be processed.
    
    Returns:
        The agent-generated response as a string.
    """
    if thread_id not in active_threads:
        write_to_log(f"Error: Thread not found - {thread_id}")
        raise ValueError("Thread not found")

    write_to_log(f"Processing message for thread {thread_id}: {user_input}")

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    try:
        result = await asyncio.to_thread(_make_request, thread_id, user_input, config)
        active_threads[thread_id].append(user_input)
        return result['response']
        
    except Exception:
        raise


if __name__ == "__main__":
    write_to_log("Starting MCP server")
    
    # Run MCP server
    mcp.run(transport='stdio')

