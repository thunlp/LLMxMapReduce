#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Host Layer
"""

import asyncio
import json
import logging
import os
from copy import deepcopy
from typing import Dict, Any, List, Optional
from pathlib import Path
import datetime
import traceback
from src.mcp_client.client import create_mcp_client
from src.data_structure import Survey

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from request.wrapper import RequestWrapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLM_Host:
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.mcp_client = {}
        self._connected = {} 
        self.config = self._load_config()
        self.available_servers_and_tools = {}
        self.all_tools = []
        self.operation_history = []
        self.conversation_history = []
        analyse_settings = self.config.get("analyse_settings", {})
        self.max_rounds = analyse_settings.get("llm_host_max_rounds", 10)
        self.skeleton_settings = self.config.get("skeleton_settings", {})
        self.base_dir = f"output/{datetime.datetime.now().strftime('%Y%m%d')}"
        self.max_interaction_rounds = 3

        self._init_llm_components()

        self.survey = None
        
    def _load_config(self):
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
            models = self.config.get("models", {})
            host_model = models.get("host_llm_model") or models.get("default_model")
            interaction_model = models.get("interaction_model") or models.get("default_model")

            infer_type = models.get("default_infer_type")

            if not host_model:
                raise ValueError("No host model specified in configuration. Please set 'host_llm_model' or 'default_model' in config/unified_config.json")
            elif not interaction_model:
                raise ValueError("No interaction model specified in configuration. Please set 'interaction_model' or 'default_model' in config/unified_config.json")
            
            if not infer_type:
                raise ValueError("No infer_type specified in configuration. Please set 'default_infer_type' in config/unified_config.json")
            
            self.host_llm_wrapper = RequestWrapper(
                model=host_model,
                infer_type=infer_type
            )
            logger.info(f"Host LLM wrapper initialized with model: {host_model}")

            self.interaction_llm_wrapper = RequestWrapper(
                model=interaction_model,
                infer_type=infer_type
            )
            logger.info(f"Interaction LLM wrapper initialized with model: {host_model}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM wrapper: {e}")
            raise
    
    async def connect(self):
        server_config = self.config.get("mcp_server_config", {})
        for server_name in server_config:
            logger.info(f"Connecting to MCP server: {server_name}")
            if server_name in self._connected and self._connected[server_name]:
                return
            
            try:
                self.mcp_client[server_name] = await create_mcp_client(server_config[server_name])
                self._connected[server_name] = True

                self.available_servers_and_tools[server_name] = await self.mcp_client[server_name].list_tools()
                self.all_tools.extend(self.available_servers_and_tools[server_name])
                logger.info(f"Successfully connected to {server_name}")
                logger.info(f"Available tools: {[tool['name'] for tool in self.available_servers_and_tools[server_name]]}")

            except Exception as e:
                logger.error(f"Failed to connect to {server_name}: {e}")
                raise
    
    async def _cleanup_after_task_completion(self):
        logger.info("Starting post-task cleanup process")

        for server_name in self.mcp_client:
            try:
                if self.mcp_client[server_name] and self._connected[server_name]:
                    logger.info(f"Gracefully disconnecting MCP client for {server_name} after task completion...")
                    try:
                        await self.mcp_client[server_name].disconnect()
                        logger.info(f"MCP client for {server_name} disconnected successfully")
                    except Exception as disconnect_error:
                        # Log the error but don't let it stop the cleanup process
                        logger.warning(f"MCP client for {server_name} disconnect had issues (continuing cleanup): {disconnect_error}")
                    finally:
                        # Always clear the client reference
                        self.mcp_client[server_name] = None

                # Step 2: Reset connection state
                self._connected[server_name] = False

            except Exception as e:
                logger.error(f"Error during post-task cleanup: {e}")
                # Force cleanup even if there were errors
                self.mcp_client[server_name] = None
                self._connected[server_name] = False
                self.operation_history = []
                self.conversation_history = []

            # Step 3: Clear operation history for next task
            self.operation_history = []
            self.conversation_history = []

            logger.info("Post-task cleanup completed successfully")

    async def disconnect(self):
        """
        Safely disconnect from MCP server with improved error handling
        """
        logger.info("Starting LLMHost disconnect process")

        for server_name in self.mcp_client:
            try:
                if self.mcp_client[server_name] and self._connected[server_name]:
                    logger.info(f"Disconnecting MCP client for {server_name}...")
                    try:
                        await self.mcp_client[server_name].disconnect()
                        logger.info(f"MCP client for {server_name} disconnected successfully")
                    except Exception as disconnect_error:
                        logger.warning(f"MCP client disconnect had issues (this is often normal): {disconnect_error}")
                        # Continue with cleanup even if disconnect had issues
                    finally:
                        self.mcp_client[server_name] = None

                self._connected[server_name] = False
                logger.info(f"LLMHost for {server_name} disconnected successfully")

            except Exception as e:
                logger.error(f"Error during LLMHost disconnect: {e}")
                # Force cleanup even if there were errors
                self.mcp_client[server_name] = None
                self._connected[server_name] = False

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

    def get_search_result_file_path(self, topic) -> str:

        filename = f"output/{datetime.datetime.now().strftime('%Y%m%d')}/{topic}/search/crawl_results_{topic}.json"

        return filename
    
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

                if action in [tool["name"] for tool in self.all_tools]:
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
                    breakpoint()
                    server_name = decision.get("server_name").replace(" ", "_").lower()
                    tool_name = decision.get("tool_name") 
                    logger.info(f"Next Action: {tool_name} of {server_name}.")
                    
                    if not tool_name:
                        logger.warning("Tool name not specified in decision")
                        continue

                    if tool_name == "group_papers":
                        
                        title = self.operation_history[-1]["result"]["title"],
                        if isinstance(title, tuple):
                            title = str(title[0])
                        search_result_file = os.path.join(self.base_dir, title, "search", f"crawl_results_{title}.json")

                        with open(search_result_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            if 'topic' in json_data:
                                json_data['title'] = json_data['topic']
                            if 'crawl_progress' in json_data:
                                json_data['papers'] = json_data['crawl_progress']
                                for i in range(len(json_data['papers'])):
                                    json_data['papers'][i]['txt'] = json_data['papers'][i].get('content', '') 
                            json_data['papers'] = [paper for paper in json_data['papers'] if paper.get('title')]

                            try:
                                self.survey = Survey(json_data) if isinstance(json_data, dict) else json_data
                            except Exception as e:
                                logger.error(traceback.format_exc())
                                logger.error(f"Error creating Survey object from search results: {e}")
                                breakpoint()

                    if server_name in ["group_server", "skeleton_init_server", "digest_server"]:
                        arguments = {
                            "survey": self.survey.to_json(),
                            "config": self.config
                        }
                    elif server_name == "skeleton_refine_server":
                        # TODO：
                        arguments = {
                            "survey": self.survey.to_json(),
                            "config": self.config,
                            "convolution_layer": "6",
                            "convolution_kernel_size": "3",
                            "convolution_result_num": "10",
                            "top_k": "6",
                            "self_refine_count": "0",
                            "self_refine_best_of": "3",
                        }
                    elif server_name == "writing_server":
                        arguments = {
                            "survey": self.survey.to_json(),
                            "config": self.config,
                            "output_file": os.path.join(self.base_dir, self.survey.title, f"{self.survey.title}.json")
                        }
                    else:
                        arguments = decision.get("arguments", {})

                    tool_result = await self._execute_tool_call(server_name, tool_name, arguments)

                    if tool_name in ["group_papers", "skeleton_init", "digest_generation", "skeleton_refine"]:
                        self.survey = Survey.from_json(json.dumps(tool_result))
                        with open(os.path.join(self.base_dir, self.survey.title, f"{tool_name}_result.json"), "w", encoding="utf-8") as sf:
                            sf.write(self.survey.to_json())
                    
                    history_arguments = {}
                    history_arguments["survey"] = deepcopy(json.loads(self.survey.to_json())) if self.survey else {}
                    papers = json.loads(arguments.get("survey", "{}")).get("papers", [])
                    history_arguments["survey"]["papers"] = [
                        {
                            "title": paper["title"],
                            "query": paper["meta_data"]["query"]
                        } 
                        if paper.get("meta_data") else
                        {
                            "title": paper["title"],
                            "abstract": paper["abstract"]
                        }
                        for paper in papers
                        ]

                    if tool_name in ["group_papers", "digest_generation"]:
                        result_to_be_history = self.survey.digests.to_dict()
                    elif tool_name == "skeleton_init":
                        result_to_be_history = json.loads(self.survey.skeleton.to_json())["raw_skeleton"]
                    elif tool_name == "skeleton_refine":
                        result_to_be_history = self.survey.skeleton.all_skeleton()
                    else:
                        result_to_be_history = tool_result

                    self.operation_history.append({ 
                        "round": round_num,
                        "action": "call_tool",
                        "tool_name": tool_name,
                        "result": result_to_be_history
                    })
                
                elif action == "request_info":
                    message = decision.get("message", "Need more information")
                    logger.info(f"LLM requests info: {message}")

                    self.operation_history.append({
                        "round": round_num,
                        "action": "request_info",
                        "message": message
                    })

                elif action == "interaction":
                    if server_name == "search_server":
                        provided_input = tool_result
                    elif server_name == "digest_server":
                        provided_input = self.survey.skeleton.raw_skeleton
                    elif server_name == "skeleton_refine_server":
                        provided_input = self.survey.skeleton.all_skeleton()
                    else:
                        logger.error(f"Only support interaction after search / digest / skeleton_refine. Unsupported tool: {tool_name}")
                    
                    logger.info(f"The system output: \n\n{provided_input}")

                    message = {
                        "interaction_finished": 0,
                        "modified_output": provided_input
                    }

                    interaction_round = 0

                    while int(message["interaction_finished"]) == 0 and interaction_round < self.max_interaction_rounds:
                        breakpoint()
                        # TODO: 
                        user_feedback = input(f"\n\n> Are you satisfied with it?\n>")
                        
                        interaction_prompt = self.config["prompts"].get("interaction", f"The provided input:\n{provided_input}\n\nThe user feedback:\n{user_feedback}").format(provided_input=provided_input, user_feedback=user_feedback)

                        response = await self.interaction_llm_wrapper.async_request(interaction_prompt)

                        message = self._parse_llm_response(response)
                        logger.info(f"LLM interaction message: {message['interaction_finished']}")
                        logger.info(f"LLM modified the system output as below: \n{message.get('modified_output', 'NO MODIFIED!')}")
                        interaction_round += 1

                    # 记录交互请求
                    self.operation_history.append({
                        "round": round_num,
                        "action": "interact",
                        "interaction_result": "Please go to the next step!" # TODO: 这句提示词写得太矬了需要修改
                    })
                
                else:
                    logger.warning(f"Unknown action: {action}")
                    continue
                    
            except Exception as e:
                logger.error(f"Error in decision round {round_num}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
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

            response = await self.host_llm_wrapper.async_request(self.conversation_history)

            self.conversation_history.append({"role": "assistant", "content": response})

            decision = self._parse_llm_response(response)

            logger.info(f"LLM decision: {decision}")
            return decision

        except Exception as e:
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Error calling LLM for decision: {e}")
            breakpoint()
            return None

    def _build_system_prompt(self) -> str:
        tools_info = []
        tools_description = {}
        for server_name in self.available_servers_and_tools:
            tools = self.available_servers_and_tools[server_name]

            for tool in tools:
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

            tools_description[server_name] = "\n\n".join(tools_info)

        prompts = self.config.get("prompts", {})
        system_prompt_template = prompts.get("llm_host_system",
            "You are an intelligent task-handling assistant capable of using multiple tools to accomplish the user’s tasks.\n\nAvailable tools:\n1.  **Search Server**: \n{search_server_tools}\n2.  **Group Server**: \n{group_server_tools}\n3.  **Skeleton Init Server**: \n{skeleton_init_server_tools}\n4.  **Digest Server:**: \n{digest_server_tools}\n5.  **Skeleton Refine Server**:\n{skeleton_refine_server_tools}")

        system_prompt = system_prompt_template.format(
            search_server_tools = tools_description.get("search_server", ""),
            group_server_tools = tools_description.get("group_server", ""),
            skeleton_init_server_tools = tools_description.get("skeleton_init_server", ""),
            digest_server_tools = tools_description.get("digest_server", ""),
            skeleton_refine_server_tools = tools_description.get("skeleton_refine_server", ""),
            writing_server_tools = tools_description.get("writing_server", "")
            )

        return system_prompt

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
                    state_parts.append(f"  {round_info}. Use tool: {tool_name}, result: {result_summary}")
                elif action == "request_info":
                    message = op.get("message", "")
                    state_parts.append(f"  {round_info}. Request: {message}")
                elif action == "error":
                    error = op.get("error", "")
                    state_parts.append(f"  {round_info}. Error: {error}")
        else:
            state_parts.append("\n Hstory: none")

        state_parts.append(f"\nPlease analyze the current status and decide the next step:")

        return "\n".join(filter(None, state_parts))

    def _fix_brace_balance(self, json_str: str) -> str:
        """Fix unbalanced braces in JSON string"""
        if not json_str:
            return json_str
            
        open_count = json_str.count('{')
        close_count = json_str.count('}')
        diff = open_count - close_count
        
        if diff > 0:
            fixed = json_str + '}' * diff
            logger.warning(f"Fixed JSON by adding {diff} closing brace(s): {json_str[:50]}...")
            return fixed
        elif diff < 0:
            fixed = json_str[:diff]
            logger.warning(f"Fixed JSON by removing {abs(diff)} closing brace(s): {json_str[:50]}...")
            return fixed

        return json_str

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        cleaned_response = response.strip()
        if not cleaned_response or cleaned_response.lower() in ['none', 'null', '']:
            logger.info("LLM returned None/empty response, ending task")
            return {"action": "complete", "result": "Task completed - LLM indicated no further action needed"}
        
        json_to_parse = None
        import re
        json_pattern = r'```(?:json|mermaid|yaml|yml)?\s*(.*?)\s*```'
        match = re.search(json_pattern, cleaned_response, re.DOTALL)
        if match:
            json_to_parse = match.group(1).strip()

        if not json_to_parse:
            if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                json_to_parse = cleaned_response
        if not json_to_parse:
            brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            match = re.search(brace_pattern, cleaned_response, re.DOTALL)
            if match:
                json_to_parse = match.group(0)

        if json_to_parse:
            try:
                json_to_parse = self._fix_brace_balance(json_to_parse) 

                try:
                    return json.loads(json_to_parse)
                except json.JSONDecodeError as e:
                    fixed_json = json_to_parse.replace('\n', '\\n')

                    return json.loads(fixed_json)

            except json.JSONDecodeError as e:
                pass

        try:
            breakpoint()
            logger.warning(f"Could not parse LLM response as JSON: {cleaned_response}")
            return {"action": "complete", "result": f"Task completed - Unable to parse LLM response: {cleaned_response[:100]}..."}

        except Exception as e:
            breakpoint()
            logger.error(f"Unexpected error parsing LLM response: {e}")
            return {"action": "complete", "result": f"Task completed - Unexpected parsing error: {str(e)}"}
        

    async def _execute_tool_call(self, server_name, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.info(f"Executing tool: {tool_name} of {server_name}")
            tool_names = [tool["name"] for tool in self.available_servers_and_tools[server_name]]
            if tool_name not in tool_names:
                raise ValueError(f"Unknown tool: {tool_name}. Available tools: {tool_names}")

            result = await self.mcp_client[server_name].call_tool(tool_name, arguments)

            logger.info(f"Tool {tool_name} executed successfully")
            return result

        except Exception as e:
            logger.error(traceback.format_exc())
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

    async with LLM_Host() as host:
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
        traceback.print_exc()
        sys.exit(1)
