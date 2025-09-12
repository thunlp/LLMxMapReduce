#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Host Layer
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from .llm_search_mcp_client import create_mcp_client

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from request.wrapper import RequestWrapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMHost:
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.mcp_client = None
        self._connected = False
        self.env_config = self._load_environment_config()
        self.available_tools = []
        self.operation_history = []
        self.conversation_history = []
        analyse_settings = self.env_config.get("analyse_settings", {})
        self.max_rounds = analyse_settings.get("llm_host_max_rounds", 10)
        
        self._init_llm_components()
        
    def _load_environment_config(self):
        try:
            config_paths = [
                "config/unified_config.json",
                os.path.join(os.path.dirname(__file__), "..", "..", "config", "unified_config.json")
            ]

            for config_path in config_paths:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)

            logger.error("Environment config file not found! Please ensure config/unified_config.json exists")
            raise FileNotFoundError("Configuration file config/unified_config.json is required but not found")
        except Exception as e:
            logger.error(f"Failed to load environment config: {e}")
            return {}
    
    def _init_llm_components(self):
        try:
            models = self.env_config.get("models", {})
            model = models.get("host_llm_model") or models.get("default_model")
            infer_type = models.get("default_infer_type")

            if not model:
                raise ValueError("No model specified in configuration. Please set 'host_llm_model' or 'default_model' in config/unified_config.json")
            if not infer_type:
                raise ValueError("No infer_type specified in configuration. Please set 'default_infer_type' in config/unified_config.json")
            
            self.llm_wrapper = RequestWrapper(
                model=model,
                infer_type=infer_type
            )
            logger.info(f"LLM wrapper initialized with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM wrapper: {e}")
            raise
    
    async def connect(self):
        if self._connected:
            return
            
        try:
            server_config = self._prepare_server_config()
            self.mcp_client = await create_mcp_client(server_config)
            self._connected = True
            
            self.available_tools = await self.mcp_client.list_tools()
            
            logger.info("Successfully connected to LLM MCP Server")
            logger.info(f"Available tools: {[tool['name'] for tool in self.available_tools]}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    def _prepare_server_config(self) -> Dict[str, Any]:
        env_vars = {
            "PYTHONPATH": ".",
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
        }

        api_keys = self.env_config.get("api_keys", {})

        openai_config = api_keys.get("openai", {})
        if openai_config.get("api_key"):
            env_vars["OPENAI_API_KEY"] = openai_config["api_key"]
        if openai_config.get("base_url"):
            env_vars["OPENAI_BASE_URL"] = openai_config["base_url"]
            env_vars["OPENAI_API_BASE"] = openai_config["base_url"]

        search_engines = api_keys.get("search_engines", {})
        if search_engines.get("serpapi_key"):
            env_vars["SERPAPI_KEY"] = search_engines["serpapi_key"]
            env_vars["SERP_API_KEY"] = search_engines["serpapi_key"]
        if search_engines.get("bing_subscription_key"):
            env_vars["BING_SEARCH_V7_SUBSCRIPTION_KEY"] = search_engines["bing_subscription_key"]

        if openai_config.get("api_key"):
            env_vars["GOOGLE_API_KEY"] = openai_config["api_key"]

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent

        return {
            "command": "python",
            "args": ["-m", "src.search.llm_search_mcp_server"],
            "env": env_vars,
            "cwd": str(project_root)
        }
    
    async def _cleanup_after_task_completion(self):
        logger.info("Starting post-task cleanup process")

        try:
            if self.mcp_client and self._connected:
                logger.info("Gracefully disconnecting MCP client after task completion...")
                try:
                    await self.mcp_client.disconnect()
                    logger.info("MCP client disconnected successfully")
                except Exception as disconnect_error:
                    logger.warning(f"MCP client disconnect had issues (continuing cleanup): {disconnect_error}")
                finally:
                    self.mcp_client = None

            self._connected = False

            self.operation_history = []
            self.conversation_history = []

            logger.info("Post-task cleanup completed successfully")

        except Exception as e:
            logger.error(f"Error during post-task cleanup: {e}")
            self.mcp_client = None
            self._connected = False
            self.operation_history = []
            self.conversation_history = []

    async def disconnect(self):
        """
        Safely disconnect from MCP server with improved error handling
        """
        logger.info("Starting LLMHost disconnect process")

        try:
            if self.mcp_client and self._connected:
                logger.info("Disconnecting MCP client...")
                try:
                    await self.mcp_client.disconnect()
                    logger.info("MCP client disconnected successfully")
                except Exception as disconnect_error:
                    logger.warning(f"MCP client disconnect had issues (this is often normal): {disconnect_error}")
                finally:
                    self.mcp_client = None

            self._connected = False
            logger.info("LLMHost disconnected successfully")

        except Exception as e:
            logger.error(f"Error during LLMHost disconnect: {e}")
            self.mcp_client = None
            self._connected = False
    
    async def process_task(self, task_description: str, context: str = "") -> Dict[str, Any]:
        if not self._connected:
            await self.connect()
            
        try:
            logger.info(f"Starting task processing: '{task_description}'")

            self.operation_history = []

            result = await self._llm_decision_loop(task_description, context)
            
            logger.info(f"Task processing completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in task processing: {e}")
            raise
    
    async def _llm_decision_loop(self, task_description: str, context: str) -> Dict[str, Any]:
        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"=== Decision Round {round_num}/{self.max_rounds} ===")
            
            try:
                decision = await self._call_llm_for_decision(task_description, context, round_num)

                if not decision:
                    logger.warning(f"No decision received in round {round_num}, ending task")
                    return {
                        "status": "completed",
                        "result": "Task ended - No decision from LLM",
                        "rounds_used": round_num,
                        "operation_history": self.operation_history
                    }

                action = decision.get("action")

                if action in [tool["name"] for tool in self.available_tools]:
                    logger.info(f"Converting tool name action '{action}' to call_tool format")
                    decision = {
                        "action": "call_tool",
                        "tool_name": action,
                        "arguments": decision.get("arguments", {})
                    }
                    action = "call_tool"

                if action == "call_tool" and decision.get("tool_name") is None:
                    logger.info("LLM indicated None tool, ending task")
                    await self._cleanup_after_task_completion()

                    return {
                        "status": "completed",
                        "result": "Task completed - LLM indicated no further tools needed",
                        "rounds_used": round_num,
                        "operation_history": self.operation_history
                    }
                
                if action == "complete":
                    logger.info("LLM decided to complete the task")
                    result = decision.get("result", "Task completed")

                    await self._cleanup_after_task_completion()

                    return {
                        "status": "completed",
                        "result": result,
                        "rounds_used": round_num,
                        "operation_history": self.operation_history
                    }
                
                elif action == "call_tool":
                    tool_name = decision.get("tool_name")
                    arguments = decision.get("arguments", {})
                    
                    if not tool_name:
                        logger.warning("Tool name not specified in decision")
                        continue
                    
                    tool_result = await self._execute_tool_call(tool_name, arguments)
        
                    self.operation_history.append({
                        "round": round_num,
                        "action": "call_tool",
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": tool_result
                    })
                
                elif action == "request_info":
                    message = decision.get("message", "Need more information")
                    logger.info(f"LLM requests info: {message}")
             
                    self.operation_history.append({
                        "round": round_num,
                        "action": "request_info",
                        "message": message
                    })
                
                else:
                    logger.warning(f"Unknown action: {action}")
                    continue
                    
            except Exception as e:
                logger.error(f"Error in decision round {round_num}: {e}")
                self.operation_history.append({
                    "round": round_num,
                    "action": "error",
                    "error": str(e)
                })
        
        logger.warning(f"Reached maximum rounds ({self.max_rounds})")

        await self._cleanup_after_task_completion()

        return {
            "status": "max_rounds_reached",
            "result": "Task processing reached maximum rounds limit",
            "rounds_used": self.max_rounds,
            "operation_history": self.operation_history
        }

    async def _call_llm_for_decision(self, task_description: str, context: str, round_num: int) -> Optional[Dict[str, Any]]:
        try:
            system_prompt = self._build_system_prompt()

            current_state = self._build_current_state(task_description, context, round_num)
            
            if round_num == 1:
                self.conversation_history = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_state}
                ]
            else:
                self.conversation_history.append({"role": "user", "content": current_state})

            response = await self.llm_wrapper.async_request(self.conversation_history)

            self.conversation_history.append({"role": "assistant", "content": response})

            decision = self._parse_llm_response(response)

            logger.info(f"LLM decision: {decision}")
            return decision

        except Exception as e:
            logger.error(f"Error calling LLM for decision: {e}")
            return None

    def _build_system_prompt(self) -> str:
        tools_info = []
        for tool in self.available_tools:
            name = tool.get("name", "")
            description = tool.get("description", "")

            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            params_info = []
            for prop, prop_info in properties.items():
                prop_type = prop_info.get("type", "string")
                prop_desc = prop_info.get("description", "")
                is_required = prop in required
                req_marker = " (must)" if is_required else " (optional)"
                params_info.append(f"  - {prop}: {prop_type}{req_marker} - {prop_desc}")

            params_str = "\n".join(params_info) if params_info else "  non-parameters"
            tools_info.append(f"- {name}: {description}\n{params_str}")

        tools_description = "\n\n".join(tools_info)

        prompts = self.env_config.get("prompts", {})
        system_prompt_template = prompts.get("llm_host_system",
            "You are an intelligent task-handling assistant capable of using multiple tools to accomplish the user’s tasks.\n\nAvailable tools:\n{tools_description}")

        return system_prompt_template.format(tools_description=tools_description)

    def _build_current_state(self, task_description: str, context: str, round_num: int) -> str:
        state_parts = [
            f"Task description:{task_description}",
            f"Task context:{context}" if context else "",
            f"Rounds: {round_num}/{self.max_rounds}"
        ]

        if self.operation_history:
            state_parts.append("\ncontext history:")
            for i, op in enumerate(self.operation_history, 1):
                round_info = op.get("round", i)
                action = op.get("action", "unknown")

                if action == "call_tool":
                    tool_name = op.get("tool_name", "unknown")
                    result = op.get("result", {})
                    result_summary = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    state_parts.append(f"  {round_info}. Use tool: {tool_name}, result：{result_summary}")
                elif action == "request_info":
                    message = op.get("message", "")
                    state_parts.append(f"  {round_info}. Request：{message}")
                elif action == "error":
                    error = op.get("error", "")
                    state_parts.append(f"  {round_info}. Error：{error}")
        else:
            state_parts.append("\n Hstory: none")

        state_parts.append(f"\nPlease analyze the current status and decide the next step:")

        return "\n".join(filter(None, state_parts))

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:

        try:
            cleaned_response = response.strip()

            if not cleaned_response or cleaned_response.lower() in ['none', 'null', '']:
                logger.info("LLM returned None/empty response, ending task")
                return {"action": "complete", "result": "Task completed - LLM indicated no further action needed"}

            if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                return json.loads(cleaned_response)

            import re
            json_pattern = r'```(?:json)?\s*(.*?)\s*```'
            match = re.search(json_pattern, cleaned_response, re.DOTALL)
            if match:
                json_content = match.group(1).strip()
                if json_content:
                    return json.loads(json_content)

            brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            match = re.search(brace_pattern, cleaned_response, re.DOTALL)
            if match:
                return json.loads(match.group(0))

            logger.warning(f"Could not parse LLM response as JSON: {cleaned_response}")
            return {"action": "complete", "result": f"Task completed - Unable to parse LLM response: {cleaned_response[:100]}..."}

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.warning(f"Response content: {response}")
            return {"action": "complete", "result": f"Task completed - JSON parsing error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response: {e}")
            return {"action": "complete", "result": f"Task completed - Unexpected parsing error: {str(e)}"}

    async def _execute_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:

        try:
            logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")


            tool_names = [tool["name"] for tool in self.available_tools]
            if tool_name not in tool_names:
                raise ValueError(f"Unknown tool: {tool_name}. Available tools: {tool_names}")


            result = await self.mcp_client.call_tool(tool_name, arguments)

            logger.info(f"Tool {tool_name} executed successfully")
            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.disconnect()
        except Exception as e:
            logger.warning(f"Error during context manager exit (this is often normal during shutdown): {e}")
        return False



async def process_task(task_description: str, context: str = "") -> Dict[str, Any]:

    async with LLMHost() as host:
        return await host.process_task(task_description, context)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python llm_host.py <task_description> [context]")
        sys.exit(1)

    task_description = sys.argv[1]
    context = sys.argv[2] if len(sys.argv) > 2 else ""

    print(f"🤖 Starting intelligent task processing: {task_description}")
    if context:
        print(f"📝 Context: {context}")
    print("-" * 50)

    try:
        result = asyncio.run(process_task(task_description, context))
        print(f"\n✅ Task completed!")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Rounds used: {result.get('rounds_used', 0)}")
        print(f"Result: {result.get('result', 'No result')}")
    except Exception as e:
        print(f"\n❌ Task failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
