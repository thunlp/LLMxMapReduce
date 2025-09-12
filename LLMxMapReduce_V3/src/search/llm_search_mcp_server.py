#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Server Layer
"""


import asyncio
import json
import logging
import sys
import os
import time
import re
import traceback
from typing import Dict, Any, List
import json
import datetime

try:
    if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
import mcp.server.stdio

try:
    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    AsyncWebCrawler = None
    CacheMode = None
    CrawlerRunConfig = None


from .LLM_search import LLM_search
try:
    from .clean.html_extrator import CommonCrawlWARCExtractor, JusTextExtractor, ResiliparseExtractor
    HTML_CLEANER_AVAILABLE = True
except ImportError as e:
    HTML_CLEANER_AVAILABLE = False
    CommonCrawlWARCExtractor = None
    JusTextExtractor = None
    ResiliparseExtractor = None

from request import RequestWrapper

import logging.handlers

log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(log_dir, exist_ok=True)


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'mcp_server.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

_html_extractor = None
if HTML_CLEANER_AVAILABLE:
    try:
        _html_extractor = CommonCrawlWARCExtractor(algorithm=JusTextExtractor())
        logger.info("✅ HTML cleaner initialized with JusText algorithm")
    except Exception as e:
        logger.warning(f"❌ Failed to initialize HTML cleaner: {e}")
        logger.info("Will fall back to basic HTML cleaning using regex")
        _html_extractor = None
else:
    logger.warning("❌ HTML cleaner not available, will use basic text extraction")

app = Server("llm-search-server")

def load_server_config():

    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'unified_config.json')

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        api_keys = config.get("api_keys", {})

        openai_config = api_keys.get("openai", {})
        if openai_config.get("api_key"):
            os.environ["OPENAI_API_KEY"] = openai_config["api_key"]
        if openai_config.get("base_url"):
            os.environ["OPENAI_BASE_URL"] = openai_config["base_url"]

        search_engines = api_keys.get("search_engines", {})

        if not os.environ.get("SERPAPI_KEY") and search_engines.get("serpapi_key"):
            os.environ["SERPAPI_KEY"] = search_engines["serpapi_key"]
        elif os.environ.get("SERPAPI_KEY"):
            logger.info(f"✅ SERPAPI_KEY : {os.environ['SERPAPI_KEY'][:10]}...")
        else:
            logger.warning("❌ SERPAPI_KEY can't find.")

        if not os.environ.get("BING_SEARCH_V7_SUBSCRIPTION_KEY") and search_engines.get("bing_subscription_key"):
            os.environ["BING_SEARCH_V7_SUBSCRIPTION_KEY"] = search_engines["bing_subscription_key"]
        elif os.environ.get("BING_SEARCH_V7_SUBSCRIPTION_KEY"):
            logger.info(f"✅ BING_SEARCH_V7_SUBSCRIPTION_KEY is ready.")
        else:
            logger.warning("❌ BING_SEARCH_V7_SUBSCRIPTION_KEY can't find.")

        serpapi_key = os.environ.get("SERPAPI_KEY")
        bing_key = os.environ.get("BING_SEARCH_V7_SUBSCRIPTION_KEY")

        models = config.get("models", {})
        search_settings = config.get("search_settings", {})
        timeout_settings = config.get("timeout_settings", {})
        crawling_settings = config.get("crawling_settings", {})
        mcp_settings = config.get("mcp_settings", {})
        prompts = config.get("prompts", {})

        logger.info(f"📝 Model setting: {models.get('default_model', 'N/A')}")

        required_models = ["default_model", "default_infer_type", "content_analysis_model",
                          "similarity_model", "page_refine_model"]
        for model_key in required_models:
            if not models.get(model_key):
                raise ValueError(f"Missing required model configuration: {model_key}")

        server_config = {
            "default_model": models.get("default_model"),
            "default_infer_type": models.get("default_infer_type"),
            "content_analysis_model": models.get("content_analysis_model"),
            "similarity_model": models.get("similarity_model"),
            "page_refine_model": models.get("page_refine_model"),
            "default_engine": search_settings.get("default_engine", "google"),
            "default_query_count": search_settings.get("default_query_count", 30),
            "default_each_query_result": search_settings.get("default_each_query_result", 10),
            "default_total_urls": search_settings.get("default_total_urls", 200),
            "default_top_n": search_settings.get("default_top_n", 70),
            "default_similarity_threshold": search_settings.get("default_similarity_threshold", 30),
            "default_min_length": search_settings.get("default_min_length", 100),
            "default_max_length": search_settings.get("default_max_length", 1000000),
            "llm_request_timeout": timeout_settings.get("llm_request_timeout", 30),
            "web_search_timeout": timeout_settings.get("web_search_timeout", 0),
            "crawling_timeout": timeout_settings.get("crawling_timeout", 0),
            "single_url_crawl_timeout": timeout_settings.get("single_url_crawl_timeout", 60),
            "content_analysis_timeout": timeout_settings.get("content_analysis_timeout", 30),
            "similarity_scoring_timeout": timeout_settings.get("similarity_scoring_timeout", 30),
            "abstract_generation_timeout": timeout_settings.get("abstract_generation_timeout", 30),
            "abstract_tasks_wait_timeout": timeout_settings.get("abstract_tasks_wait_timeout", 300),
            "max_concurrent_crawls": crawling_settings.get("max_concurrent_crawls", 10),
            "page_timeout": crawling_settings.get("page_timeout", 60),
            "retry_attempts": crawling_settings.get("retry_attempts", 3),
            "cache_mode": crawling_settings.get("cache_mode", "BYPASS"),
            "query_cache_dir": f"output/{datetime.now().strftime('%Y%m%d')}/topic/search/query_cache",
            "url_cache_dir": f"output/{datetime.now().strftime('%Y%m%d')}/topic/search/url_cache",
            "prompts": prompts
        }

        logger.info(f"Environment config loaded successfully")
        logger.info(f"Server config: {server_config}")
        return server_config

    except Exception as e:
        logger.error(f"Failed to load environment config: {e}")
        logger.error("Configuration file config/unified_config.json is required but not found or invalid")
        raise FileNotFoundError("Configuration file config/unified_config.json is required but not found or invalid")

SERVER_CONFIG = load_server_config()
llm_search_instances = {}

def proc_title_to_str(origin_title: str) -> str:
    if not origin_title:
        return ""

    title = origin_title.lower().strip()
    title = title.replace("-", "_")
    title = re.sub(r'[^\w\s\_]', '', title)
    title = title.replace(" ", "_")
    title = re.sub(r'_{2,}', '_', title)
    return title

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    words = text.split()
    return int(len(words) * 1.3)

def extract_abstract(text: str, max_length: int = 500) -> str:
    if not text:
        return ""

    cleaned_text = re.sub(r'\s+', ' ', text.strip())

    if len(cleaned_text) <= max_length:
        return cleaned_text

    truncated = cleaned_text[:max_length]
    last_period = truncated.rfind('.')

    if last_period > max_length * 0.7:
        return truncated[:last_period + 1]
    else:
        return truncated + "..."
@app.list_resources()
async def list_resources() -> List[Resource]:
    return [
        Resource(
            uri="llm://search/prompts",
            name="LLM Search Prompts",
            description="LLM search prompts",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> List[TextContent]:
    if uri == "llm://search/prompts":
        prompts = SERVER_CONFIG.get("prompts", {})
        return [TextContent(
            type="text",
            text=json.dumps(prompts, ensure_ascii=False, indent=2)
        )]
    else:
        raise ValueError(f"Unknown resource: {uri}")

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="generate_search_queries",
            description="Generate optimized search queries based on LLM. The research topic must be provided, and the output should include the number of generated queries and the file save path, but not the actual query contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "topic"
                    },
                    "description": {
                        "type": "string",
                        "description": "detailed descriptions"
                    }
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="web_search",
            description="Execute a web search and collect URLs. A topic must be provided, and the output should include the number of URLs retrieved and the file save path, without returning the actual URL list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Main topic for relevance filtering"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of most relevant URLs returned",
                        "default": 200
                    }
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="crawl_urls",
            description="Crawl URL contents and perform intelligent processing. A research topic must be provided, and the output should include the number of successfully crawled URLs, the number of final results, and the file save path, without returning the actual article contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Research topic for content filtering and similarity scoring"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of highest-quality results returned",
                        "default": 70
                    }
                },
                "required": ["topic"]
            }
        )
    ]
@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:

    global llm_search_instances

    try:
        if name == "generate_search_queries":
            result = await _generate_search_queries(
                arguments["topic"],
                arguments.get("description", ""),
                arguments.get("model")  
            )
        elif name == "web_search":
            result = await _web_search(
                arguments.get("query_file_path"), 
                arguments["topic"],
                arguments.get("top_n"),
                arguments.get("engine")
            )

        elif name == "crawl_urls":
            result = await _crawl_urls(
                arguments["topic"],
                arguments.get("url_file_path"),
                arguments.get("top_n"),
                arguments.get("model"),
                arguments.get("similarity_threshold"),
                arguments.get("min_length"),
                arguments.get("max_length")
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

def _get_llm_search_instance(model: str = None, engine: str = None):
    global llm_search_instances

    if model is None:
        model = SERVER_CONFIG["default_model"]
    if engine is None:
        engine = SERVER_CONFIG["default_engine"]

    infer_type = SERVER_CONFIG["default_infer_type"]
    each_query_result = SERVER_CONFIG["default_each_query_result"]

    key = f"{model}_{engine}_{infer_type}"
    if key not in llm_search_instances:
        import os

        serpapi_key = os.environ.get("SERPAPI_KEY")
        bing_key = os.environ.get("BING_SEARCH_V7_SUBSCRIPTION_KEY")


        if not serpapi_key and not bing_key:
            try:
                env_config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'environment_config.json')
                with open(env_config_path, 'r', encoding='utf-8') as f:
                    env_config = json.load(f)

                search_engines = env_config.get("api_keys", {}).get("search_engines", {})
                if search_engines.get("serpapi_key"):
                    os.environ["SERPAPI_KEY"] = search_engines["serpapi_key"]

                if search_engines.get("bing_subscription_key"):
                    os.environ["BING_SEARCH_V7_SUBSCRIPTION_KEY"] = search_engines["bing_subscription_key"]

            except Exception as reload_e:
                logger.error(f"❌load setting failed: {reload_e}")

        try:
            logger.info(f"🚀 Start Search Agent: {key}")
            llm_search_instances[key] = LLM_search(
                model=model,
                infer_type=infer_type,
                engine=engine,
                each_query_result=each_query_result
            )
            logger.info(f"✅ Search Agent success finish: {key}")
        except Exception as e:
            logger.error(f"❌ Search Agent failed: {e}")
            raise e

    return llm_search_instances[key]

async def _generate_search_queries(topic: str, description: str = "", model: str = None) -> Dict[str, Any]:
    logger.info(f"Generating search queries for topic: {topic}")

    try:
        if model is None:
            model = SERVER_CONFIG["default_model"]

        infer_type = SERVER_CONFIG.get("default_infer_type", "OpenAI")

        llm_search = _get_llm_search_instance(model=model)

        import asyncio
        import functools
        loop = asyncio.get_event_loop()

        query_count = SERVER_CONFIG.get("default_query_count", 30)

        get_queries_func = functools.partial(
            llm_search.get_queries,
            topic=topic,
            description=description,
            query_count=query_count
        )

        try:
            queries = await asyncio.wait_for(
                loop.run_in_executor(None, get_queries_func),
                timeout=SERVER_CONFIG.get("llm_request_timeout", 30)
            )
        except asyncio.TimeoutError:
            logger.error(f"LLM query generation timed out for topic: {topic}")
            queries = [
                topic,
                f"{topic} research",
                f"{topic} analysis",
                f"{topic} study"
            ]

        query_file_path = _save_queries_to_file(queries, topic, description)

        result = {
            "topic": topic,
            "description": description,
            "model": model,
            "queries": queries,
            "query_count": len(queries),
            "query_file_path": query_file_path,
            "processing_metadata": {
                "model": model,
                "method": "llm_generation",
                "timestamp": "2025-01-23",
                "query_file_saved": query_file_path is not None
            }
        }

        return result

    except Exception as e:
        logger.error(f"Error generating queries: {e}")
        print(e)
        return
async def _web_search(query_file_path: str = None, topic: str = "", top_n: int = None, engine: str = None) -> Dict[str, Any]:

    queries = _load_queries_from_file(query_file_path, topic)
    logger.info(f"Performing web search for {len(queries)} queries")

    try:
        if top_n is None:
            top_n = SERVER_CONFIG["default_total_urls"] 
        if engine is None:
            engine = SERVER_CONFIG["default_engine"]

        try:
            llm_search = _get_llm_search_instance(engine=engine)
            if llm_search is None:
                raise ValueError("Failed to create LLM_search instance")
        except Exception as e:
            logger.error(f"Failed to get LLM_search instance: {e}")
            return {
                "topic": topic,
                "queries": queries,
                "engine": engine or SERVER_CONFIG["default_engine"],
                "urls": [],
                "url_count": 0,
                "top_n": top_n,
                "processing_metadata": {
                    "engine": engine,
                    "query_count": len(queries),
                    "result_count": 0,
                    "method": "error_fallback",
                    "error": str(e)
                }
            }

        try:
            logger.info(f"🚀 start batch_web_search, query number: {len(queries)}")
            urls = llm_search.batch_web_search(queries, topic, top_n)
            logger.info(f"✅ batch_web_search finished, return URL numbers: {len(urls)}")
        except Exception as e:
            logger.error(f"❌ batch_web_search failed: {e}")
            logger.error(f"Fail information: {traceback.format_exc()}")
            urls = []
        url_file_path = _save_urls_to_file(urls, topic, queries)

        result = {
            "topic": topic,
            "queries": queries,
            "engine": engine,
            "urls": urls,
            "url_count": len(urls),
            "url_file_path": url_file_path,
            "top_n": top_n,
            "processing_metadata": {
                "engine": engine,
                "query_count": len(queries),
                "result_count": len(urls),
                "method": "batch_web_search",
                "url_file_saved": url_file_path is not None
            }
        }

        return result

    except Exception as e:
        logger.error(f"Error in web search: {e}")
        url_file_path = _save_urls_to_file([], topic, queries)

        return {
            "topic": topic,
            "queries": queries,
            "engine": engine or SERVER_CONFIG["default_engine"],
            "urls": [],
            "url_count": 0,
            "url_file_path": url_file_path,
            "top_n": top_n or SERVER_CONFIG["default_total_urls"],
            "processing_metadata": {
                "engine": engine or SERVER_CONFIG["default_engine"],
                "query_count": len(queries),
                "result_count": 0,
                "method": "fallback",
                "error": str(e),
                "url_file_saved": url_file_path is not None
            }
        }

async def _crawl_urls(topic: str, url_file_path: str = None, top_n: int = None, model: str = None,
                     similarity_threshold: float = None, min_length: int = None, max_length: int = None) -> Dict[str, Any]:

    url_list = _load_urls_from_file(url_file_path, topic)
    logger.info(f"Starting crawling process for {len(url_list)} URLs with topic: {topic}")

    try:
        if top_n is None:
            top_n = SERVER_CONFIG["default_top_n"]
        if model is None:
            model = SERVER_CONFIG["default_model"]
        if similarity_threshold is None:
            similarity_threshold = SERVER_CONFIG["default_similarity_threshold"]
        if min_length is None:
            min_length = SERVER_CONFIG["default_min_length"]
        if max_length is None:
            max_length = SERVER_CONFIG["default_max_length"]

        if not CRAWL4AI_AVAILABLE:
            raise ImportError("crawl4ai is not available")
        if RequestWrapper is None:
            raise ImportError("RequestWrapper is not available")

        import time
        import re

        content_model = SERVER_CONFIG.get("content_analysis_model", model)
        infer_type = SERVER_CONFIG.get("default_infer_type", "OpenAI")
        request_wrapper = RequestWrapper(model=content_model, infer_type=infer_type)

        process_start_time = time.time()
        stage_time = process_start_time

        crawling_timeout = SERVER_CONFIG.get("crawling_timeout", 0)


        try:
            if crawling_timeout > 0:
                crawl_results = await asyncio.wait_for(
                    _crawl_urls_stage(topic, url_list),
                    timeout=crawling_timeout
                )
            else:
                crawl_results = await _crawl_urls_stage(topic, url_list)
            logger.info(f"Stage 1 - Crawling completed in {time.time() - stage_time:.2f} seconds, with {len(crawl_results)} results")
        except asyncio.TimeoutError:
            logger.error(f"URL crawling stage timed out after {crawling_timeout} seconds")
            logger.error("⚠️ Attempting to retrieve partial results from incremental save file...")

            try:
                import os
                import json
                incremental_file_path = _get_incremental_crawl_file_path(topic)
                logger.info(f"Attempt to restore results from incremental file: {incremental_file_path}")

                if os.path.exists(incremental_file_path):
                    with open(incremental_file_path, 'r', encoding='utf-8') as f:
                        incremental_data = json.load(f)

                    crawl_progress = incremental_data.get("crawl_progress", [])
                    logger.info(f"Found {len(crawl_progress)} completed crawl results from incremental file")

                    crawl_results = []
                    for progress in crawl_progress:
                        if progress.get("success", False):
                            crawl_results.append({
                                "url": progress.get("url", ""),
                                "error": False,
                                "raw_content": progress.get("content", ""),
                                "title": progress.get("title", ""),
                                "date": progress.get("date", ""),
                                "timestamp": progress.get("timestamp", ""),
                                "is_recovered": True
                            })
                        else:
                            crawl_results.append({
                                "url": progress.get("url", ""),
                                "error": True,
                                "raw_content": progress.get("error_message", "Unknown error"),
                                "timestamp": progress.get("timestamp", "")
                            })

                    logger.info(f"✅ Successfully restored {len(crawl_results)} partial results")
                else:
                    logger.error(f"Incremental file does not exist: {incremental_file_path}")
                    crawl_results = []

                logger.error(f"📊 Timeout analysis:")
                logger.error(f"  - Total URLs to crawl: {len(url_list)}")
                logger.error(f"  - Completed URLs: {len(crawl_results)}")
                logger.error(f"  - Completion rate: {len(crawl_results)/len(url_list)*100:.1f}%")
                logger.error(f"  - Timeout setting: {crawling_timeout} seconds")
                logger.error(f"  - Average time per URL: {crawling_timeout / len(url_list):.2f} seconds")

                suggested_timeout = len(url_list) * 60
                logger.error(f"  - Suggested timeout: {suggested_timeout} seconds")

            except Exception as e:
                logger.error(f"Error during partial result recovery: {e}")
                crawl_results = []
        stage_time = time.time()

        logger.info("Stage 2 - Content filtering with relaxed settings")

        filtered_results = []
        error_count = 0
        success_count = 0

        for result in crawl_results:
            is_error = result.get("error", False)
            content = result.get("cleaned_content", "") or result.get("raw_content", "") or result.get("content", "")

            cleaning_info = result.get("cleaning_info", {})
            title = result.get("title", "")
            language = result.get("language", "UNKNOWN")

            if is_error:
                error_count += 1
                logger.warning(f"Error result for URL {result.get('url', 'unknown')}: {content[:100]}...")
            else:
                success_count += 1

            enhanced_result = {
                "url": result.get("url", ""),
                "title": title or result.get("title", "Unknown"), 
                "content": content,
                "raw_content": result.get("raw_content", ""),
                "date": result.get("date", ""),
                "length": len(content),
                "language": language,
                "is_error": is_error,
                "original_error": result.get("error", False),
                "cleaning_info": cleaning_info
            }
            filtered_results.append(enhanced_result)

        logger.info(f"Stage 2 completed - processed {len(filtered_results)} results (success: {success_count}, errors: {error_count})")

        if error_count > 0 and success_count == 0:
            logger.warning(f"⚠️ All {error_count} crawl results failed! This will likely result in 0 final results.")
        elif error_count > 0:
            logger.warning(f"⚠️ {error_count} out of {len(crawl_results)} crawl results failed.")
        stage_time = time.time()
        # to be update
        logger.info("Stage 3 - Simplified similarity scoring")
        scored_results = []
        for result in filtered_results:
            result["similarity_score"] = 90.0
            scored_results.append(result)

        logger.info(f"Stage 3 completed - scored {len(scored_results)} results")
        stage_time = time.time()

        print(f"DEBUG: scored_results count: {len(scored_results)}")
        if scored_results:
            print(f"DEBUG: First result keys: {list(scored_results[0].keys())}")
            print(f"DEBUG: First result similarity_score: {scored_results[0].get('similarity_score', 'N/A')}")
            print(f"DEBUG: First result content length: {len(scored_results[0].get('content', ''))}")
            print(f"DEBUG: First result is_error: {scored_results[0].get('is_error', 'N/A')}")
            print(f"DEBUG: First result content preview: {scored_results[0].get('content', '')[:200]}...")

        valid_results = []
        for result in scored_results:
            content = result.get("content", "")
            if content and len(content.strip()) > 0:
                # to be update
                valid_results.append(result)
                logger.info(f"Kept result: {result.get('url', 'unknown')}, content_length={len(content)}, stripped_length={len(content.strip())}")
            else:
                logger.warning(f"Filtered out result with invalid content: {result.get('url', 'unknown')}, content_length={len(content)}, stripped_length={len(content.strip()) if content else 0}")


        print(f"DEBUG: valid_results count after content filtering: {len(valid_results)}")

        if len(valid_results) > 0:
            first_result = valid_results[0]
            content = first_result.get("content", "")
            print(f"DEBUG: First valid result analysis:")
            print(f"  - URL: {first_result.get('url', 'unknown')}")
            print(f"  - Original length: {len(content)}")
            print(f"  - Stripped length: {len(content.strip())}")
            print(f"  - Is error: {first_result.get('is_error', False)}")
            print(f"  - Content preview (first 200 chars): '{content[:200]}...'")
            print(f"  - Content preview (last 200 chars): '...{content[-200:]}'")

            import re
            whitespace_count = len(re.findall(r'\s', content))
            meaningful_chars = len(re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]', content))
            print(f"  - Whitespace characters: {whitespace_count}")
            print(f"  - Meaningful characters: {meaningful_chars}")

        final_results = valid_results[:top_n] 
        print(f"DEBUG: final_results count: {len(final_results)}")
        logger.info(f"Stage 4 - Result processing completed in {time.time() - stage_time:.2f} seconds")

        if len(final_results) == 0:
            logger.error("🚨 FINAL RESULTS IS ZERO! Debugging information:")
            logger.error(f"  - Original crawl_results: {len(crawl_results)}")
            logger.error(f"  - Filtered_results: {len(filtered_results)}")
            logger.error(f"  - Scored_results: {len(scored_results)}")
            logger.error(f"  - Valid_results: {len(valid_results)}")
            logger.error(f"  - Success_count: {success_count}")
            logger.error(f"  - Error_count: {error_count}")

            for i, result in enumerate(crawl_results[:5]):
                raw_content = result.get('raw_content', '')
                logger.error(f"  - Crawl result {i+1}:")
                logger.error(f"    URL: {result.get('url', 'N/A')}")
                logger.error(f"    Error: {result.get('error', False)}")
                logger.error(f"    Content length: {len(raw_content)}")
                logger.error(f"    Stripped length: {len(raw_content.strip()) if raw_content else 0}")
                if raw_content:
                    logger.error(f"    Content preview: '{raw_content[:200]}...'")
                    if raw_content.startswith("Error:"):
                        logger.error(f"    ⚠️ This is an error result")
                    else:
                        logger.error(f"    ✅ This appears to be valid content")

            logger.error("🔍 Analysis of why all results were filtered:")
            all_errors = all(r.get("error", False) for r in crawl_results)
            all_empty = all(len(r.get("raw_content", "").strip()) == 0 for r in crawl_results)

            if all_errors:
                logger.error("  🚨 ALL results are error results")
            elif all_empty:
                logger.error("  🚨 ALL results have empty content after stripping")
            else:
                error_count_check = sum(1 for r in crawl_results if r.get("error", False))
                empty_count = sum(1 for r in crawl_results if len(r.get("raw_content", "").strip()) == 0)
                logger.error(f"  🚨 Mixed issues: {error_count_check} errors, {empty_count} empty content")
        else:
            logger.info(f"✅ Successfully generated {len(final_results)} final results")

        total_time = time.time() - process_start_time
        logger.info(f"Total crawling process completed in {total_time:.2f} seconds")

        main_result = {
            "title": topic,
            "papers": final_results
        }

        detailed_result = {
            "title": topic,
            "total_urls": len(url_list),
            "crawl_results": len(crawl_results),
            "filtered_results": len(filtered_results),
            "scored_results": len(scored_results),
            "papers": final_results,
            "final_count": len(final_results),
            "processing_metadata": {
                "model": model,
                "similarity_threshold": similarity_threshold,
                "min_length": min_length,
                "max_length": max_length,
                "top_n": top_n,
                "total_time": total_time,
                "success": True
            },
            "llm_mapreduce_format": main_result
        }

        try:

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/{datetime.datetime.now().strftime('%Y%m%d')}/{topic}/search/crawl_results_{timestamp}.json"

            error_analysis = {
                "total_errors": error_count,
                "total_success": success_count,
                "error_details": [],
                "error_types": {}
            }

            for result in crawl_results:
                if result.get("error", False):
                    error_detail = {
                        "url": result.get("url", "unknown"),
                        "error_message": result.get("raw_content", ""),
                        "timestamp": result.get("timestamp", "")
                    }
                    error_analysis["error_details"].append(error_detail)

                    error_msg = result.get("raw_content", "")
                    if "timeout" in error_msg.lower():
                        error_type = "timeout"
                    elif "connection" in error_msg.lower():
                        error_type = "connection"
                    elif "none" in error_msg.lower() and "attribute" in error_msg.lower():
                        error_type = "parsing_error"
                    elif "403" in error_msg or "forbidden" in error_msg.lower():
                        error_type = "access_denied"
                    elif "404" in error_msg or "not found" in error_msg.lower():
                        error_type = "not_found"
                    else:
                        error_type = "other"

                    error_analysis["error_types"][error_type] = error_analysis["error_types"].get(error_type, 0) + 1

            debug_info = {
                "raw_crawl_results": crawl_results,
                "processed_filtered_results": filtered_results,
                "processed_scored_results": scored_results,
                "error_analysis": error_analysis
            }
            detailed_result["debug_info"] = debug_info

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(detailed_result, f, ensure_ascii=False, indent=2)

            logger.info(f"Results saved to {filename}")
            logger.info(f"Error analysis: {error_analysis['error_types']}")
            detailed_result["saved_file"] = filename

            if error_count > 0:
                error_filename = f"output/{datetime.datetime.now().strftime('%Y%m%d')}/{topic}/search/crawl_errors_{timestamp}.json"
                with open(error_filename, 'w', encoding='utf-8') as f:
                    json.dump(error_analysis, f, ensure_ascii=False, indent=2)
                logger.info(f"Error report saved to {error_filename}")
                detailed_result["error_report_file"] = error_filename

        except Exception as e:
            logger.error(f"Failed to save results to JSON: {e}")

        return detailed_result

    except Exception as e:
        logger.error(f"Error in crawling pipeline: {e}")
        return {
            "topic": topic,
            "total_urls": len(url_list),
            "crawl_results": 0,
            "filtered_results": 0,
            "scored_results": 0,
            "final_results": [],
            "final_count": 0,
            "processing_metadata": {
                "model": model,
                "similarity_threshold": similarity_threshold,
                "min_length": min_length,
                "max_length": max_length,
                "top_n": top_n,
                "success": False,
                "error": str(e)
            }
        }

_current_incremental_file_path = None

def _get_incremental_crawl_file_path(topic: str, create_new: bool = False) -> str:
    global _current_incremental_file_path

    if _current_incremental_file_path is None or create_new:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"output/{datetime.datetime.now().strftime('%Y%m%d')}/{topic}/search/crawl_results_{topic}.json"
        _current_incremental_file_path = filename

    return _current_incremental_file_path

def _load_existing_crawl_results(file_path: str) -> Dict[str, Any]:
    import json
    import os

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load existing crawl results: {e}")

    return {
        "topic": "",
        "total_urls": 0,
        "crawl_results": 0,
        "filtered_results": 0,
        "scored_results": 0,
        "final_results": [],
        "crawl_progress": []
    }

async def _generate_abstract_llm(content: str, url: str, file_path: str, url_index: int) -> str:

    try:
        abstract_model = SERVER_CONFIG.get("abstract_generation_model", "gemini-2.5-flash")
        infer_type = SERVER_CONFIG.get("default_infer_type", "OpenAI")

        request_wrapper = RequestWrapper(model=abstract_model, infer_type=infer_type)

        prompts = SERVER_CONFIG.get("prompts", {})
        prompt_template = prompts.get("abstract_generation", "Please summarize the following content:\n\n{content}")

        max_content_length = 8000 
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        prompt = prompt_template.format(content=content)

        logger.info(f"Begin generating LLM summaries for URLs: {url}")
        abstract_timeout = SERVER_CONFIG.get("abstract_generation_timeout", 30)

        try:
            abstract_llm = await asyncio.wait_for(
                asyncio.to_thread(request_wrapper.completion, prompt),
                timeout=abstract_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"LLM summary generation timed out ({abstract_timeout}秒): {url}")
            raise Exception(f"Abstract generation timeout after {abstract_timeout} seconds")

        abstract_llm = abstract_llm.strip()
        if len(abstract_llm) > 1000:
            abstract_llm = abstract_llm[:1000] + "..."

        await _update_abstract_llm_in_file(file_path, url_index, abstract_llm, "completed")

        logger.info(f"✅ LLM summary generation finished: {url}")
        return abstract_llm

    except Exception as e:
        logger.error(f"❌ LLM summary generation failed:  {url}: {e}")
        await _update_abstract_llm_in_file(file_path, url_index, f"Error: {str(e)}", "failed")
        return f"Error: {str(e)}"

async def _update_abstract_llm_in_file(file_path: str, url_index: int, abstract_llm: str, status: str):

    import json
    import os
    import time
    import platform

    def _acquire_file_lock(f):
        if platform.system() == "Windows":
            try:
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            except ImportError:
                pass
        else:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass

    def _release_file_lock(f):
        if platform.system() == "Windows":
            try:
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except ImportError:
                pass
        else:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass

    max_retries = 3
    retry_delay = 0.05

    for attempt in range(max_retries):
        try:
            with open(file_path, 'r+', encoding='utf-8') as f:
                _acquire_file_lock(f)

                try:
                    f.seek(0)
                    data = json.load(f)
                    if url_index < len(data.get("crawl_progress", [])):
                        data["crawl_progress"][url_index]["abstract_llm"] = abstract_llm
                        data["crawl_progress"][url_index]["abstract_llm_status"] = status

                        f.seek(0)
                        f.truncate()
                        json.dump(data, f, ensure_ascii=False, indent=2)

                        logger.debug(f"update abstract_llm successed: {url_index}")
                        return
                    else:
                        logger.error(f"URL is out of range: {url_index}")
                        return

                finally:
                    _release_file_lock(f)

        except (json.JSONDecodeError, OSError, IOError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"update abstract_llm failed, retry {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(retry_delay * (2 ** attempt))
            else:
                logger.error(f"update abstract_llm failed: {e}")
        except Exception as e:
            logger.error(f"update abstract_llm failed: {e}")
            break

def _save_incremental_crawl_result(file_path: str, crawl_result: Dict[str, Any], topic: str, total_urls: int) -> int:

    import json
    import os

    try:
        existing_data = _load_existing_crawl_results(file_path)

        existing_data["topic"] = topic
        existing_data["total_urls"] = total_urls
        existing_data["crawl_results"] = len(existing_data["crawl_progress"]) + 1

        raw_content = crawl_result.get("raw_content", "")
        cleaned_content = crawl_result.get("cleaned_content", "")

        main_content = cleaned_content if cleaned_content else raw_content

        cleaning_info = crawl_result.get("cleaning_info", {})

        abstract = ""
        if main_content and not crawl_result.get("error", False):
            cleaned_for_abstract = main_content.strip()
            if len(cleaned_for_abstract) > 2000:
                truncated = cleaned_for_abstract[:2000]
                last_period = truncated.rfind('.')
                if last_period > 1600:
                    abstract = truncated[:last_period + 1]
                else:
                    abstract = truncated + "..."
            else:
                abstract = cleaned_for_abstract

        save_data = {
            "url": crawl_result.get("url", ""),
            "success": not crawl_result.get("error", False),
            "content_length": len(main_content),
            "timestamp": crawl_result.get("timestamp", ""),
            "error_message": raw_content if crawl_result.get("error", False) else "",
            "content": main_content,
            "raw_content": raw_content,
            "cleaned_content": cleaned_content,
            "title": crawl_result.get("title", ""),
            "language": crawl_result.get("language", "UNKNOWN"),
            "date": crawl_result.get("date", ""),
            "cleaning_info": cleaning_info,
            "abstract": abstract,
            "abstract_llm": "",
            "abstract_llm_status": "pending" 
        }

        new_index = len(existing_data["crawl_progress"])

        existing_data["crawl_progress"].append(save_data)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        if cleaning_info.get("method") != "none":
            logger.info(f"Saved crawl result with {cleaning_info.get('method')} cleaning for URL: {crawl_result.get('url', 'N/A')}")
        else:
            logger.debug(f"Saved crawl result (no cleaning) for URL: {crawl_result.get('url', 'N/A')}")

        return new_index

    except Exception as e:
        logger.error(f"Failed to save incremental crawl result: {e}")
        return -1

async def _crawl_urls_stage(topic: str, url_list: List[str]) -> List[Dict[str, Any]]:
    import asyncio

    if not CRAWL4AI_AVAILABLE:
        raise ImportError("crawl4ai is not available")

    MAX_CONCURRENT_CRAWLS = SERVER_CONFIG.get("max_concurrent_crawls", 10)
    input_queue = asyncio.Queue()
    output_queue = asyncio.Queue()
    total_items = len(url_list)

    abstract_tasks = []

    incremental_file_path = _get_incremental_crawl_file_path(topic, create_new=True)
    logger.info(f"Incremental crawl results will be saved to:{incremental_file_path}")

    for url in url_list:
        await input_queue.put((url, topic))

    async def consumer():
        consumer_id = id(asyncio.current_task())
        processed_count = 0

        while True:
            try:
                url, topic = input_queue.get_nowait()
                try:
                    result = await _crawl_single_url(url, topic)

                    result["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    url_index = _save_incremental_crawl_result(incremental_file_path, result, topic, total_items)

                    await output_queue.put(result)
                    processed_count += 1

                    if (not result.get("error", False) and
                        url_index >= 0 and
                        result.get("cleaned_content") or result.get("raw_content")):

                        content_for_abstract = result.get("cleaned_content") or result.get("raw_content", "")
                        if content_for_abstract.strip():
                            task = asyncio.create_task(_generate_abstract_llm(
                                content_for_abstract,
                                url,
                                incremental_file_path,
                                url_index
                            ))
                            abstract_tasks.append(task)

                    remaining = input_queue.qsize()
                    if processed_count % 10 == 0 or remaining == 0:
                        logger.info(f"Consumer {consumer_id}: has done {processed_count} URLs, remaining: {remaining}/{total_items}")

                except Exception as e:
                    logger.error(f"Consumer {consumer_id}: fetch url failed {url}: {e}")
                    import datetime
                    error_result = {
                        "topic": topic,
                        "url": url,
                        "raw_content": f"Error: {e}",
                        "error": True,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    error_index = _save_incremental_crawl_result(incremental_file_path, error_result, topic, total_items)
                    await output_queue.put(error_result)
                finally:
                    input_queue.task_done()
            except asyncio.QueueEmpty:
                if processed_count > 0:
                    logger.info(f"Consumer {consumer_id}: has done，in total {processed_count} URLs")
                break

    consumers = [asyncio.create_task(consumer()) for _ in range(MAX_CONCURRENT_CRAWLS)]


    start_time = time.time()
    try:
        queue_timeout = len(url_list) * 60 + 300
        logger.info(f"Queue wait timeout setting: {queue_timeout} seconds")

        await asyncio.wait_for(input_queue.join(), timeout=queue_timeout)
        end_time = time.time()
        logger.info(f"All URLs have been crawled, time taken: {end_time - start_time:.2f} seconds")
    except asyncio.TimeoutError:
        logger.error(f"Queue wait timeout ({queue_timeout} seconds), forcing termination of the crawling process")
    except Exception as e:
        logger.error(f"Error {e}")
    finally:
        for consumer_task in consumers:
            if not consumer_task.done():
                consumer_task.cancel()

        await asyncio.gather(*consumers, return_exceptions=True)

        if abstract_tasks:
            abstract_wait_timeout = SERVER_CONFIG.get("abstract_tasks_wait_timeout", 300)
            logger.info(f"Waiting for {len(abstract_tasks)} abstract generation tasks to complete, timeout: {abstract_wait_timeout} seconds")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*abstract_tasks, return_exceptions=True),
                    timeout=abstract_wait_timeout
                )
                logger.info("Abstract generation succeed")
            except asyncio.TimeoutError:
                logger.warning(f"Abstract generation task wait timed out ({abstract_wait_timeout} seconds), canceling remaining tasks")

                for task in abstract_tasks:
                    if not task.done():
                        task.cancel()
            except Exception as e:
                logger.error(f"Error: {e}")

    results = []
    while not output_queue.empty():
        results.append(await output_queue.get())

    return results

def _clean_html_content(html_content: str, url: str) -> Dict[str, Any]:

    def basic_clean(content):
        import re
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    if HTML_CLEANER_AVAILABLE and _html_extractor:
        try:
            extracted = _html_extractor.extract(html_content)

            if extracted and extracted.get("text"):
                return {
                    "text": extracted["text"],
                    "language": extracted.get("language", "UNKNOWN"),
                    "cleaned": True,
                    "error": False,
                    "method": "advanced"
                }
        except Exception as e:
            logger.debug(f"Advanced HTML cleaning failed for URL={url}: {e}")

    try:
        basic_text = basic_clean(html_content)
        return {
            "text": basic_text,
            "language": "UNKNOWN",
            "cleaned": True,
            "error": False,
            "method": "basic"
        }
    except Exception as e:
        logger.error(f"Basic HTML cleaning failed for URL={url}: {e}")
        return {
            "text": html_content,
            "language": "UNKNOWN",
            "cleaned": False,
            "error": True,
            "method": "none",
            "error_message": str(e)
        }

async def _crawl_single_url(url: str, topic: str) -> Dict[str, Any]:

    try:
        if not CRAWL4AI_AVAILABLE:
            raise ImportError("crawl4ai is not available")

        page_timeout_seconds = SERVER_CONFIG.get("page_timeout", SERVER_CONFIG.get("single_url_crawl_timeout", 60))
        page_timeout_ms = page_timeout_seconds * 1000 

        crawler_run_config = CrawlerRunConfig(
            page_timeout=page_timeout_ms,
            cache_mode=CacheMode.BYPASS
        )

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=crawler_run_config)

            if not result:
                raise Exception("Crawler returned None result")

            raw_content = None
            html_content = None
            title = ""

            if hasattr(result, 'metadata') and result.metadata:
                title = result.metadata.get('title', '')

            if not hasattr(result, 'markdown_v2') or result.markdown_v2 is None:
                logger.warning(f"No markdown_v2 found for URL={url}, trying alternative content")
                if hasattr(result, 'markdown') and result.markdown:
                    raw_content = result.markdown
                elif hasattr(result, 'cleaned_html') and result.cleaned_html:
                    raw_content = result.cleaned_html
                    html_content = result.cleaned_html
                elif hasattr(result, 'html') and result.html:
                    raw_content = result.html
                    html_content = result.html
                else:
                    raise Exception("No usable content found in crawl result")
            else:
                if hasattr(result.markdown_v2, 'raw_markdown') and result.markdown_v2.raw_markdown:
                    raw_content = result.markdown_v2.raw_markdown
                else:
                    logger.warning(f"No raw_markdown found for URL={url}, trying alternative markdown content")

                    if hasattr(result.markdown_v2, 'markdown') and result.markdown_v2.markdown:
                        raw_content = result.markdown_v2.markdown
                    else:
                        raise Exception("No usable markdown content found")

                if hasattr(result, 'html') and result.html:
                    html_content = result.html

            cleaned_info = {"method": "none", "error": False}
            cleaned_content = raw_content
            detected_language = "UNKNOWN"

            if html_content and len(html_content.strip()) > 0:
                cleaning_result = _clean_html_content(html_content, url)
                if not cleaning_result.get("error", True) and cleaning_result.get("text"):
                    cleaned_content = cleaning_result["text"]
                    detected_language = cleaning_result.get("language", "UNKNOWN")
                    cleaned_info = {
                        "method": cleaning_result.get("method", "unknown"),
                        "error": cleaning_result.get("error", False),
                        "error_message": cleaning_result.get("error_message", "")
                    }
                    logger.info(f"Content cleaned using {cleaning_result.get('method')} method for URL={url}")

            logger.info(f"Content length={len(raw_content)} (raw), {len(cleaned_content)} (cleaned) for URL={url}")

            return {
                "topic": topic,
                "url": url,
                "raw_content": raw_content,
                "cleaned_content": cleaned_content,
                "title": title,
                "language": detected_language,
                "error": False,
                "cleaning_info": cleaned_info
            }
    except Exception as e:
        logger.error(f"Crawling failed for URL={url}: {e}")
        return {
            "topic": topic,
            "url": url,
            "raw_content": f"Error: Crawling failed({e})",
            "cleaned_content": "",
            "title": "",
            "language": "UNKNOWN",
            "error": True,
            "cleaning_info": {"method": "none", "error": True, "error_message": str(e)}
        }

async def _process_filter_and_titles_stage(crawl_results: List[Dict[str, Any]], request_wrapper) -> List[Dict[str, Any]]:
    import asyncio

    MAX_CONCURRENT_PROCESSES = 10
    input_queue = asyncio.Queue()
    output_queue = asyncio.Queue()

    for data in crawl_results:
        if not data.get("error", False):
            await input_queue.put(data)

    async def processor():
        while True:
            try:
                data = input_queue.get_nowait()
                try:
                    result = await _process_filter_and_title_single(data, request_wrapper)
                    await output_queue.put(result)
                finally:
                    input_queue.task_done()
            except asyncio.QueueEmpty:
                break

    processors = [asyncio.create_task(processor()) for _ in range(MAX_CONCURRENT_PROCESSES)]

    await input_queue.join()

    for processor_task in processors:
        processor_task.cancel()

    results = []
    while not output_queue.empty():
        results.append(await output_queue.get())

    return results

async def _process_filter_and_title_single(data: Dict[str, Any], request_wrapper) -> Dict[str, Any]:
    import re

    try:
        prompt_template_response = await read_resource("llm://search/prompts")
        prompt_template = prompt_template_response[0].text
        prompts = json.loads(prompt_template)

        prompt = prompts["page_refine"].format(
            topic=data["topic"], raw_content=data["raw_content"]
        )
        res = request_wrapper.completion(prompt)

        title = re.search(r"<TITLE>(.*?)</TITLE>", res, re.DOTALL)
        content = re.search(r"<CONTENT>(.*?)</CONTENT>", res, re.DOTALL)

        if not title or not content:
            logger.warning(f"Invalid response format for URL={data.get('url', 'unknown')}, trying fallback extraction")

            raw_content = data.get("raw_content", "")
            lines = raw_content.split('\n')

            potential_title = ""
            for line in lines[:10]:
                line = line.strip()
                if line and len(line) < 200:
                    potential_title = line
                    break

            if not potential_title:
                potential_title = f"Content from {data.get('url', 'unknown')}"

            filtered_content = raw_content
            filtered_content = re.sub(r'\n\s*\n\s*\n', '\n\n', filtered_content)
            filtered_content = re.sub(r'[^\w\s\u4e00-\u9fff.,;:!?()[\]{}"\'-]', ' ', filtered_content)

            data["title"] = potential_title[:200] 
            data["content"] = filtered_content[:10000]
            data["filter_error"] = False

            logger.info(f"Used fallback extraction for URL={data.get('url', 'unknown')}")
        else:
            data["title"] = title.group(1).strip()
            data["content"] = content.group(1).strip()
            data["filter_error"] = False

        return data

    except Exception as e:
        logger.error(f"Content filtering failed for URL={data.get('url', 'unknown')}: {e}")
        data["title"] = f"Error processing: {data.get('url', 'unknown')}"
        data["content"] = f"Error: Content filtering failed({e})"
        data["filter_error"] = True
        return data

async def _process_similarity_scores_stage(filtered_results: List[Dict[str, Any]], request_wrapper) -> List[Dict[str, Any]]:

    import asyncio

    MAX_CONCURRENT_PROCESSES = 10
    input_queue = asyncio.Queue()
    output_queue = asyncio.Queue()

    for data in filtered_results:
        if not data.get("filter_error", False):
            await input_queue.put(data)

    async def scorer():
        while True:
            try:
                data = input_queue.get_nowait()
                try:
                    result = await _process_similarity_score_single(data, request_wrapper)
                    await output_queue.put(result)
                finally:
                    input_queue.task_done()
            except asyncio.QueueEmpty:
                break

    scorers = [asyncio.create_task(scorer()) for _ in range(MAX_CONCURRENT_PROCESSES)]

    await input_queue.join()

    for scorer_task in scorers:
        scorer_task.cancel()

    results = []
    while not output_queue.empty():
        results.append(await output_queue.get())

    return results

async def _process_similarity_score_single(data: Dict[str, Any], request_wrapper) -> Dict[str, Any]:
    import re

    try:
        prompt_template_response = await read_resource("llm://search/prompts")
        prompt_template = prompt_template_response[0].text
        prompts = json.loads(prompt_template)
        
        prompt = prompts["similarity_scoring"].format(
            topic=data["topic"], content=data["content"]
        )
        res = request_wrapper.completion(prompt)
        score_match = re.search(r"<SCORE>(\d+)</SCORE>", res)

        if score_match:
            data["similarity_score"] = int(score_match.group(1))
        else:
            data["similarity_score"] = 50
            logger.warning(f"No score found in response for URL={data.get('url', 'unknown')}, using default score 50")

        data["score_error"] = False
        return data

    except Exception as e:
        logger.error(f"Similarity scoring failed for URL={data.get('url', 'unknown')}: {e}")
        data["similarity_score"] = 0
        data["score_error"] = True
        return data

def _load_queries_from_file(query_file_path: str = None, topic: str = "") -> List[str]:

    try:
        import os
        import glob

        if query_file_path is None:
            cache_dir = SERVER_CONFIG.get("query_cache_dir", "query_cache")
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', cache_dir)
            if not os.path.exists(cache_dir):
                logger.warning(f"Query cache directory not found: {cache_dir}")
                return []

            pattern = os.path.join(cache_dir, "queries_*.json")
            query_files = glob.glob(pattern)

            if not query_files:
                logger.warning(f"No query files found in: {cache_dir}")
                return []

            query_file_path = max(query_files, key=os.path.getmtime)
            logger.info(f"Using latest query file: {query_file_path}")

        if not os.path.exists(query_file_path):
            logger.error(f"Query file not found: {query_file_path}")
            return []

        with open(query_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        queries = data.get("queries", [])
        logger.info(f"✅ Loaded {len(queries)} queries from: {query_file_path}")
        return queries

    except Exception as e:
        logger.error(f"❌ Failed to load queries from file: {e}")
        return []

def _load_urls_from_file(url_file_path: str = None, topic: str = "") -> List[str]:

    try:
        import os
        import glob

        if url_file_path is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'url_cache')
            if not os.path.exists(cache_dir):
                logger.warning(f"URL cache directory not found: {cache_dir}")
                return []

            pattern = os.path.join(cache_dir, "urls_*.json")
            url_files = glob.glob(pattern)

            if not url_files:
                logger.warning(f"No URL files found in: {cache_dir}")
                return []

            url_file_path = max(url_files, key=os.path.getmtime)
            logger.info(f"Using latest URL file: {url_file_path}")

        if not os.path.exists(url_file_path):
            logger.error(f"URL file not found: {url_file_path}")
            return []

        with open(url_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        urls = data.get("urls", [])
        logger.info(f"✅ Loaded {len(urls)} URLs from: {url_file_path}")
        return urls

    except Exception as e:
        logger.error(f"❌ Failed to load URLs from file: {e}")
        return []

def _save_queries_to_file(queries: List[str], topic: str, description: str = "") -> str:

    try:
        import time
        import os

        cache_dir = SERVER_CONFIG.get("query_cache_dir", "query_cache")
        save_dir = os.path.join(os.path.dirname(__file__), '..', '..', cache_dir)
        os.makedirs(save_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_topic = safe_topic.replace(' ', '_')[:30]
        filename = f"queries_{safe_topic}_{timestamp}.json"
        filepath = os.path.join(save_dir, filename)

        save_data = {
            "topic": topic,
            "description": description,
            "queries": queries,
            "query_count": len(queries),
            "timestamp": timestamp,
            "metadata": {
                "generated_by": "generate_search_queries_tool",
                "version": "1.0",
                "description": f"Search queries for topic: {topic}"
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Queries saved to: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"❌ Failed to save queries to file: {e}")
        return None

def _save_urls_to_file(urls: List[str], topic: str, queries: List[str]) -> str:

    try:
        import time
        import os

        save_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'url_cache')
        os.makedirs(save_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_topic = safe_topic.replace(' ', '_')[:30] 
        filename = f"urls_{safe_topic}_{timestamp}.json"
        filepath = os.path.join(save_dir, filename)

        save_data = {
            "topic": topic,
            "queries": queries,
            "urls": urls,
            "url_count": len(urls),
            "timestamp": timestamp,
            "metadata": {
                "generated_by": "web_search_tool",
                "version": "1.0",
                "description": f"Web search URLs for topic: {topic}"
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ URLs saved to: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"❌ Failed to save URLs to file: {e}")
        return None

def _process_and_sort_results(scored_results: List[Dict[str, Any]], top_n: int,
                             similarity_threshold: float, min_length: int, max_length: int) -> List[Dict[str, Any]]:

    filtered_results = []
    for result in scored_results:
        content_length = len(result.get("content", ""))
        score_error = result.get("score_error", False)
        similarity_score = result.get("similarity_score", 0)

        logger.info(f"Processing result: URL={result.get('url', 'Unknown')}")
        logger.info(f"  - content_length: {content_length}")
        logger.info(f"  - score_error: {score_error}")
        logger.info(f"  - similarity_score: {similarity_score}")
        logger.info(f"  - similarity_threshold: {similarity_threshold}")
        logger.info(f"  - max_length: {max_length}")

        if (not score_error and
            similarity_score >= similarity_threshold and
            content_length > 0 and content_length <= max_length):
            filtered_results.append(result)
            logger.info(f"  ✅ Result PASSED all filters")
        else:
            logger.info(f"  ❌ Result FAILED filters:")
            if score_error:
                logger.info(f"    - score_error: {score_error}")
            if similarity_score < similarity_threshold:
                logger.info(f"    - similarity_score ({similarity_score}) < threshold ({similarity_threshold})")
            if content_length <= 0:
                logger.info(f"    - content_length ({content_length}) <= 0")
            if content_length > max_length:
                logger.info(f"    - content_length ({content_length}) > max_length ({max_length})")

    filtered_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

    final_results = filtered_results[:top_n]

    formatted_results = []
    for i, result in enumerate(final_results):
        content = result.get("content", "")
        title = result.get("title", "")

        paper_data = {
            "title": title,
            "url": result.get("url", ""),
            "txt": content,
            "similarity": result.get("similarity_score", 0), 

            "bibkey": proc_title_to_str(title),
            "abstract": extract_abstract(content, 500),
            "txt_token": estimate_tokens(content),
            "txt_length": len(content),

            "source_type": "web_crawl",
            "crawl_timestamp": time.time(),
            "processing_stage": "crawl_complete"
        }
        formatted_results.append(paper_data)

    return formatted_results

async def main():
    logger.info("Starting LLM Search MCP Server...")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
