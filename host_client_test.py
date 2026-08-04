import asyncio
import json
import sys
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-4o"


class MCPClient:
    def __init__(self, model: str = MODEL):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model = model
        self.openai = OpenAI()

    # ------------------------------------------------------------------ #
    # 1. Connect to the MCP server                                         #
    # ------------------------------------------------------------------ #
    async def connect_to_server(self, server_script_path: str):
        """Spin up the MCP server as a subprocess and open a session."""
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError(
                "Server script must be a Python (.py) or JavaScript (.js) file."
            )

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None,
        )

        # Open the stdio transport and bind a ClientSession to it
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self.session.initialize()

        # List the tools the server exposes so the LLM knows what's available
        response = await self.session.list_tools()
        tool_names = [tool.name for tool in response.tools]
        print(f"\nConnected to server: {server_script_path}")
        print(f"Available tools: {tool_names}\n")

    # ------------------------------------------------------------------ #
    # 2. Send a query through the LLM → MCP tool loop                     #
    # ------------------------------------------------------------------ #
    async def process_query(self, query: str) -> str:
        """
        Pass a user query to the LLM.
        If the LLM decides to call an MCP tool, execute it and feed the
        result back so the LLM can produce a final answer.
        """
        if not self.session:
            raise RuntimeError("Not connected to a server. Call connect_to_server first.")

        # Build the tool schema list from whatever the server exposes
        tools_response = await self.session.list_tools()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools_response.tools
        ]

        messages = [{"role": "user", "content": query}]

        # Agentic loop: keep going until the LLM stops calling tools
        while True:
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message
            messages.append(assistant_message)

            # No tool calls → the LLM has a final answer
            if not assistant_message.tool_calls:
                return assistant_message.content

            # Execute each tool call the LLM requested
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"  [tool call] {tool_name}({tool_args})")

                tool_result = await self.session.call_tool(tool_name, tool_args)

                # Extract plain text from the result content blocks
                result_text = " ".join(
                    block.text
                    for block in tool_result.content
                    if isinstance(block, TextContent)
                )

                # Feed the tool result back into the conversation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    }
                )

    # ------------------------------------------------------------------ #
    # 3. Interactive chat loop (simulates the host UI)                     #
    # ------------------------------------------------------------------ #
    async def chat_loop(self):
        """
        Run a simple REPL that lets a user talk to the agent.
        This is the host layer — it owns the conversation turn by turn.
        Type 'quit' or 'exit' to stop.
        """
        print("MCP Client ready. Type your question, or 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input:
                continue

            if user_input.lower() in {"quit", "exit"}:
                print("Goodbye.")
                break

            try:
                answer = await self.process_query(user_input)
                print(f"\nAgent: {answer}\n")
            except Exception as e:
                print(f"\n[error] {e}\n")

    # ------------------------------------------------------------------ #
    # 4. Cleanup                                                           #
    # ------------------------------------------------------------------ #
    async def cleanup(self):
        """Close the MCP session and release all resources."""
        await self.exit_stack.aclose()


# ---------------------------------------------------------------------- #
# Main entry point                                                         #
# ---------------------------------------------------------------------- #
async def main():
    if len(sys.argv) < 2:
        script = sys.argv[0]
        print(f"Usage: uv run {script} <path/to/server_script.py>")
        sys.exit(1)

    server_path = sys.argv[1]
    client = MCPClient()

    try:
        await client.connect_to_server(server_path)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())