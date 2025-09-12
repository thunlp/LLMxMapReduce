#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Client Layer
"""


import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPClient:

    def __init__(self, server_config: Dict[str, Any]):
        self.server_config = server_config
        self.session = None
        self.stdio_context = None
        self._connected = False

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with improved error handling"""
        try:
            await self.disconnect()
        except Exception as e:
            logger.warning(f"Error during context manager exit (this is often normal during shutdown): {e}")
        return False

    async def connect(self):
        try:
            if self._connected:
                logger.warning("Already connected to MCP server")
                return

            logger.info("Connecting to MCP Server...")

            env_vars = self.server_config.get("env", {})

            env = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "TEMP": os.environ.get("TEMP", ""),
                "TMP": os.environ.get("TMP", ""),
                "USERPROFILE": os.environ.get("USERPROFILE", ""),
                "HOMEDRIVE": os.environ.get("HOMEDRIVE", ""),
                "HOMEPATH": os.environ.get("HOMEPATH", ""),
                "COMPUTERNAME": os.environ.get("COMPUTERNAME", ""),
                "USERNAME": os.environ.get("USERNAME", ""),
                "USERDOMAIN": os.environ.get("USERDOMAIN", ""),
            }

            if env_vars:
                for k, v in env_vars.items():
                    if v: 
                        env[k] = v

            env = {k: v for k, v in env.items() if v}
            logger.info(f"Setting environment variables: {list(env.keys())}")
            server_params = StdioServerParameters(
                command=self.server_config["command"],
                args=self.server_config.get("args", []),
                env=env
            )
            self.stdio_context = stdio_client(server_params)
            read_stream, write_stream = await self.stdio_context.__aenter__()

            self.session = ClientSession(read_stream, write_stream)
            await self.session.__aenter__()
            await self.session.initialize()

            self._connected = True
            logger.info("Successfully connected to MCP server")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        try:
            if not self._connected:
                return

            logger.info("Starting MCP client disconnect process")

            if self.session:
                try:
                    logger.debug("Clearing session reference")
                    self.session = None
                except Exception as e:
                    logger.warning(f"Error clearing session: {e}")
                    self.session = None
            if self.stdio_context:
                try:
                    logger.debug("Clearing stdio context reference")
                    self.stdio_context = None
                except Exception as e:
                    logger.warning(f"Error clearing stdio context: {e}")
                    self.stdio_context = None
            self._connected = False
            logger.info("MCP client disconnected successfully")

        except Exception as e:
            logger.error(f"Error during MCP client disconnect: {e}")
            self._connected = False
            self.session = None
            self.stdio_context = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        try:
            if not self._connected or not self.session:
                raise RuntimeError("Not connected to MCP server")

            tools = await self.session.list_tools()
            logger.debug(f"Available tools: {[tool.name for tool in tools.tools]}")

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                for tool in tools.tools
            ]

        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self._connected or not self.session:
                raise RuntimeError("Not connected to MCP server")

            logger.debug(f"Calling tool: {tool_name} with arguments: {arguments}")

            result = await self.session.call_tool(tool_name, arguments)

            if result.content and len(result.content) > 0:
                content = result.content[0]
                if isinstance(content, TextContent):
                    return json.loads(content.text)

            raise ValueError(f"No valid response received from tool {tool_name}")

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise

    async def list_resources(self) -> List[Dict[str, Any]]:
        try:
            if not self._connected or not self.session:
                raise RuntimeError("Not connected to MCP server")

            resources = await self.session.list_resources()
            logger.debug(f"Available resources: {[resource.uri for resource in resources.resources]}")

            return [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mimeType
                }
                for resource in resources.resources
            ]

        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            raise

    async def read_resource(self, uri: str) -> str:
        try:
            if not self._connected or not self.session:
                raise RuntimeError("Not connected to MCP server")

            result = await self.session.read_resource(uri)
            return result.contents[0].text if result.contents else ""

        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            raise

    @property
    def is_connected(self) -> bool:
        return self._connected

async def create_mcp_client(server_config: Dict[str, Any]) -> MCPClient:

    try:
        client = MCPClient(server_config)
        await client.connect()
        return client

    except Exception as e:
        logger.error(f"Failed to create MCP client: {e}")
        raise

async def create_mcp_client_from_config(config_path: str = "config/llm_search_mcp_config.json",
                                       server_name: str = "llm_search_mcp") -> MCPClient:
    try:
        if not os.path.isabs(config_path):
            config_path = os.path.join(os.path.abspath("."), config_path)

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        server_config = config["mcpServers"][server_name]
        return await create_mcp_client(server_config)

    except Exception as e:
        logger.error(f"Failed to create MCP client from config: {e}")
        raise

async def example_usage():
    client = None
    try:

        client = await create_mcp_client_from_config()

        tools = await client.list_tools()
        print("Available tools:", [tool["name"] for tool in tools])

        result = await client.call_tool(
            "generate_search_queries",
            {
                "topic": "machine learning optimization",
                "description": "Research on optimization techniques in machine learning"
            }
        )

        print("Tool result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        logger.error(f"Example usage failed: {e}")
    finally:
        if client:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(example_usage())
