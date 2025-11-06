#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional
from pathlib import Path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.mcp_host.host import LLM_Host
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnalyseLLMHostInterface:

    def __init__(self,
                 base_dir: str = "new/test",
                 config_path: Optional[str] = None):

        self.base_dir = Path(base_dir)
        self.config_path = config_path
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir = self.base_dir / "config"
        self.config_dir.mkdir(exist_ok=True)

        self._load_environment_config()

        if not hasattr(self, 'env_config') or self.env_config is None:
            logger.error("env_config not properly loaded, using defaults")
            self.env_config = {
                "models": {"default_model": "gemini-2.5-flash", "default_infer_type": "OpenAI"},
                "analyse_settings": {"max_interaction_rounds": 3, "max_context_messages": 10}
            }
        try:
            self.max_interaction_rounds = self.env_config.get("analyse_settings", {}).get("max_interaction_rounds", 3)
            self.llm_model = self.env_config.get("models", {}).get("default_model", "gemini-2.5-flash")
            self.llm_infer_type = self.env_config.get("models", {}).get("default_infer_type", "OpenAI")
        except Exception as e:
            logger.error(f"Failed to load environment config: {e}")
            self.max_interaction_rounds = 3
            self.llm_model = "gemini-2.5-flash"
            self.llm_infer_type = "OpenAI"

        self.conversation_history = []
        self.llm_host = LLM_Host()

        self.logger = logging.getLogger(__name__)

        for handler in logging.root.handlers:
            if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
                try:
                    handler.stream.reconfigure(encoding='utf-8')
                except:
                    pass
        self._load_config()

    async def cleanup(self):
        try:
            if hasattr(self, 'llm_host') and self.llm_host:
                try:
                    await self.llm_host.disconnect()
                except Exception as disconnect_error:
                    self.logger.warning(f"LLM host disconnect had issues (continuing cleanup): {disconnect_error}")
                finally:
                    self.llm_host = None
            self.logger.info("Resource cleanup completed")
        except Exception as e:
            self.logger.error(f"Error occurred while cleaning up resources: {e}")
            if hasattr(self, 'llm_host'):
                self.llm_host = None

    def _load_environment_config(self):
        try:
            config_paths = [
                "config/unified_config.json",
                os.path.join(os.path.dirname(__file__), "..", "..", "config", "unified_config.json")
            ]

            for config_path in config_paths:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self.env_config = json.load(f)
                    logger.info(f"Environment config loaded from: {config_path}")
                    self._set_environment_variables()
                    return
            logger.warning("Environment config file not found, using defaults")
            self.env_config = {
                "models": {
                    "default_model": "gemini-2.0-flash",
                    "default_infer_type": "OpenAI"
                },
                "analyse_settings": {
                    "max_interaction_rounds": 3,
                    "max_context_messages": 10,
                    "web_search_timeout": 30000.0,
                    "crawl_urls_timeout": 30000.0,
                    "mcp_tool_timeout": 30000.0
                }
            }
        except Exception as e:
            logger.error(f"Failed to load environment config: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.env_config = {
                "models": {
                    "default_model": "gemini-2.5-flash",
                    "default_infer_type": "OpenAI"
                },
                "analyse_settings": {
                    "max_interaction_rounds": 3,
                    "max_context_messages": 10,
                    "web_search_timeout": 30000.0,
                    "crawl_urls_timeout": 30000.0,
                    "mcp_tool_timeout": 30000.0
                }
            }

    def _set_environment_variables(self):
        try:
            api_keys = self.env_config.get("api_keys", {})
            openai_config = api_keys.get("openai", {})
            if openai_config.get("api_key"):
                os.environ["OPENAI_API_KEY"] = openai_config["api_key"]
                logger.info("✅ OPENAI_API_KEY configured")
            if openai_config.get("base_url"):
                os.environ["OPENAI_BASE_URL"] = openai_config["base_url"]
                logger.info("✅ OPENAI_BASE_URL configured")
            search_engines = api_keys.get("search_engines", {})
            if search_engines.get("serpapi_key"):
                os.environ["SERPAPI_KEY"] = search_engines["serpapi_key"]
                logger.info(f"✅ SERPAPI_KEY configured: {search_engines['serpapi_key'][:10]}...")

            if search_engines.get("bing_subscription_key"):
                os.environ["BING_SEARCH_V7_SUBSCRIPTION_KEY"] = search_engines["bing_subscription_key"]
                logger.info("✅ BING_SEARCH_V7_SUBSCRIPTION_KEY configured")

        except Exception as e:
            logger.error(f"Failed to set environment variables: {e}")

        logger.info(f"AnalyseLLMHostInterface initialized:")
        logger.info(f"  - Base directory: {self.base_dir}")
        logger.info(f"  - Using LLMHost for intelligent task processing")

    async def analyse(self, topic: str, description: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Starting intelligent task analysis for topic: '{topic}'")
        self.conversation_history.clear()

        try:
            logger.info("=== Search Resourses ===")
            task_description = f"Execute literature search task:{topic}"
            context_segments = [f"Topic: {topic}"]
            if description:
                context_segments.append(f"Description: {description}")
            context = "\n".join(context_segments)

            result = await self.llm_host.process_task(task_description, context)

            logger.info("✅ Intelligent analysis completed successfully")
            logger.info(f"Status: {result.get('status', 'unknown')}")
            logger.info(f"Rounds used: {result.get('rounds_used', 0)}")

            return result

        except Exception as e:
            logger.error(f"Error in intelligent task analysis: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _load_config(self):
        try:
            if self.config_path and os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "search": {
                        "default_top_n": 20,
                        "default_engine": "google",
                        "similarity_threshold": 80
                    },
                    "interaction": {
                        "timeout_seconds": 0,  # No time limits
                        "auto_continue": False
                    }
                }
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load config, using defaults: {e}")
            self.config = {}


async def analyse_with_llm_host(task: str, description: Optional[str] = None) -> Dict[str, Any]:

    analyser = AnalyseLLMHostInterface()
    try:
        return await analyser.analyse(task, description)
    finally:
        await analyser.cleanup()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyse_llm_host.py <topic> [description]")
        sys.exit(1)

    topic = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"🤖 Start intelligent analysis: {topic}")
    if description:
        print(f"📝 Description: {description}")
    print("-" * 50)

    try:
        import asyncio
        analysis_result = asyncio.run(analyse_with_llm_host(topic, description))
        print(f"\n✅ Intelligent analysis finished！")
        print(f"Status: {analysis_result.get('status', 'unknown')}")
        print(f"Rounds: {analysis_result.get('rounds_used', 0)}")
        print(f"Results: {analysis_result.get('result', 'No result')}")
    except Exception as e:
        print(f"\n❌ Intelligent analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
