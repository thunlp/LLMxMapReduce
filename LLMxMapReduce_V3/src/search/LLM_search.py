import os
import re
import traceback
import json
from typing import Optional, Literal, List, Dict
import requests
import sys
import logging
from tenacity import retry, stop_after_attempt, before_log, retry_if_exception_type

project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

from request import RequestWrapper
from src.prompts import (
    QUERY_EXPAND_PROMPT_WITH_ABSTRACT,
    QUERY_EXPAND_PROMPT_WITHOUT_ABSTRACT,
    LLM_CHECK_PROMPT,
    SNIPPET_FILTER_PROMPT,
)

logger = logging.getLogger(__name__)


class QueryParseError(Exception):
    """Error occurred while parsing query response"""

    pass


class LLM_search:
    """
    A dynamic search engine powered by a Large Language Model (LLM). Given an article topic,
    it automatically decomposes the topic into a series of search queries, refines them
    iteratively, performs web searches based on the refined queries, and returns the search results.

    Parameters:
    -----------
    model : str, optional, default='claude-3-5-haiku-20241022'
        The specific LLM model to use for query decomposition and refinement.

    engine : Literal['google', 'baidu', 'bing'], optional, default='google'
        The search engine to use for performing web searches.

    count : int, optional, default=20
        The number of search results to retrieve per query.
        For Google, it's recommended to keep it below 100.
        For Baidu and Bing, maximum supported value is 50.

    filter_date : Optional[str], optional, default=None
        Filter out search results before a certain date.
        Date format should be 'dd/mm/yyyy', e.g., '01/01/2023'.

    max_workers : int, optional, default=10
        Maximum number of concurrent workers for processing search results.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        infer_type: Optional[str] = None,
        engine: Optional[Literal["google", "baidu", "bing"]] = None,
        each_query_result: Optional[int] = None,
        filter_date: Optional[str] = None,
        max_workers: Optional[int] = None,
    ):

        self.env_config = self._load_environment_config()

        models_config = self.env_config.get("models", {})
        search_config = self.env_config.get("search_settings", {})

        self.model = model or models_config.get("default_model", "gemini-2.5-flash")
        infer_type = infer_type or models_config.get("default_infer_type", "OpenAI")
        self.engine = engine or search_config.get("default_engine", "google")
        self.each_query_result = each_query_result or search_config.get("default_each_query_result", 7)
        self.filter_date = filter_date
        self.max_workers = max_workers or 10
        self.request_pool = RequestWrapper(
            model=self.model,
            infer_type=infer_type
        )

        self.bing_subscription_key = os.getenv('BING_SEARCH_V7_SUBSCRIPTION_KEY')
        self.bing_endpoint = os.getenv('BING_SEARCH_V7_ENDPOINT', "https://api.bing.microsoft.com/v7.0/search")
        self.serpapi_key = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")

        if not self.serpapi_key and not self.bing_subscription_key:
            api_keys = self.env_config.get("api_keys", {})
            search_engines = api_keys.get("search_engines", {})

            if search_engines.get("serpapi_key"):
                self.serpapi_key = search_engines["serpapi_key"]
                os.environ["SERPAPI_KEY"] = self.serpapi_key
                logger.info("✅ SERPAPI_KEY loaded from config file")

            if search_engines.get("bing_subscription_key"):
                self.bing_subscription_key = search_engines["bing_subscription_key"]
                os.environ["BING_SEARCH_V7_SUBSCRIPTION_KEY"] = self.bing_subscription_key
                logger.info("✅ BING_SEARCH_V7_SUBSCRIPTION_KEY loaded from config file")

        if self.serpapi_key is not None:
            logger.info(f"Using SERPAPI for web search: {self.serpapi_key[:10]}...")
        elif self.bing_subscription_key is not None:
            logger.info("Using Bing Search API for web search.")
        else:
            raise ValueError("No valid search engine key provided, please check your environment variables, SERPAPI_KEY or BING_SEARCH_V7_SUBSCRIPTION_KEY.")

    def _load_environment_config(self):
        try:
            config_paths = [
                "config/environment_config.json",
                os.path.join(os.path.dirname(__file__), "..", "..", "config", "environment_config.json")
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

    def _initialize_chat(self, topic: str, abstract: str = "", query_count: int = 20) -> list:
        """Initialize chat messages for query generation"""
        if abstract:
            prompt = QUERY_EXPAND_PROMPT_WITH_ABSTRACT.format(
                topic=topic, abstract=abstract, query_count=query_count
            )
        else:
            prompt = QUERY_EXPAND_PROMPT_WITHOUT_ABSTRACT.format(topic=topic, query_count=query_count)

        return prompt

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(QueryParseError),
        before=before_log(logger, logging.DEBUG),
    )
    def _get_llm_response(self, message) -> list:
        """Get response from LLM and parse queries

        Args:
            message: List of chat messages

        Returns:
            list: Parsed query list

        Raises:
            QueryParseError: If unable to parse queries from response
        """
        response = self.request_pool.completion(message)
        reg = r"```markdown\n([\s\S]*?)```"
        match = re.search(reg, response)
        if not match:
            raise QueryParseError(
                f"Unable to parse query list from response, current response: {response}"
            )
        queries = match.group(1).strip().split(";")
        queries = [query.replace('"', "").strip() for query in queries if query.strip()]
        return queries

    def _handle_refinement(self, queries: list) -> str:
        """Handle query refinement process

        Args:
            queries: List of queries to refine

        Returns:
            str: Refinement prompt
        """
        return LLM_CHECK_PROMPT.format(queries=queries)

    def get_queries(
        self,
        topic: str,
        description: str = "",
        query_count: Optional[int] = None,
    ) -> list:
        """Get optimized search queries for a given topic

        Args:
            topic: Research topic
            description: Optional description/context of the topic
            query_count: Number of queries to generate (uses config default if None)

        Returns:
            list: List of optimized search queries
        """
        if query_count is None:
            query_count = self.env_config.get("search_settings", {}).get("default_query_count", 30)

        messages = self._initialize_chat(topic, description, query_count)
        queries = self._get_llm_response(messages)
        logger.info(f"Final count {len(queries)}:\n{queries}")
        return queries

    def web_search(
        self,
        query: str,
    ):
        if self.serpapi_key is not None:
            return self._serpapi_web_search(query)
        elif self.bing_subscription_key is not None:
            return self._bing_web_search(query)
        else:
            raise ValueError("No valid search engine key provided, please check your environment variables, SERPAPI_KEY or BING_SEARCH_V7_SUBSCRIPTION_KEY.")
 
    def _bing_web_search(
        self,
        query: str,
    ):
        mkt = 'zh-CN'
        params = {
            'q': query.lstrip('\"').rstrip('\"'),
            'mkt': mkt,
            'count': self.each_query_result,
        }
        headers = {
            'Ocp-Apim-Subscription-Key': self.bing_subscription_key
        }

        try:
            response = requests.get(self.bing_endpoint, headers=headers, params=params)
            response.raise_for_status()
            if response.status_code == 200:
                results = response.json()
            else:
                raise ValueError(response.json())

            print(f"Search Result : {results}")
            if "webPages" not in results or "value" not in results["webPages"]:
                raise Exception(f"No results found for query: '{query}'")

            web_snippets = {}
            for idx, page in enumerate(results["webPages"]["value"]):
                redacted_version = {
                    'title': page.get('name', ''),
                    'url': page.get('url', ''),
                    'snippet': page.get('snippet', ''),
                }
                if 'dateLastCrawled' in page:
                    redacted_version['date'] = page['dateLastCrawled']
                if 'displayUrl' in page:
                    redacted_version['source'] = page['displayUrl']
                web_snippets[idx] = redacted_version

            return web_snippets

        except Exception as e:
            logger.error(f"Error during Bing search: {e}")
            raise e
    
    def _serpapi_web_search(
        self,
        query: str,
    ):
        """
        Perform a web search for a single query using the configured search engine.

        Args:
            query (str): The search query string

        Returns:
            dict: Search results containing title, URL, date, source, and snippet for each result.
                Example structure:
                {
                    "0": {
                        "title": "Article title",
                        "url": "https://example.com",
                        "date": "23 hours ago",
                        "source": "Source name",
                        "snippet": "Article snippet",
                        "snippet_highlighted_words": ["keyword"]
                    },
                    ...
                }
        """

        params = {
            "engine": self.engine,
            "q": query.lstrip('"').rstrip('"'),
            "api_key": self.serpapi_key,
        }

        if self.engine == "google":
            params["google_domain"] = "google.com"
            params["num"] = self.each_query_result
            if self.filter_date is not None:
                params["tbs"] = f"cdr:1,cd_min:{self.filter_date}"

        elif self.engine == "baidu":
            params["rn"] = self.each_query_result
            if self.filter_date is not None:
                params["gpc"] = f"cdr:1,cd_min:{self.filter_date}"

        elif self.engine == "bing":
            params["count"] = self.each_query_result
            if self.filter_date is not None:
                params["filters"] = f"cdr:1,cd_min:{self.filter_date}"

        response = requests.get("https://serpapi.com/search.json", params=params)

        if response.status_code == 200:
            results = response.json()
        else:
            raise ValueError(response.json())

        if "organic_results" not in results.keys():
            if self.filter_date is not None:
                raise Exception(
                    f"No results found for query: '{query}' with filtering on date={self.filter_date}. Use a less restrictive query or do not filter on year."
                )
            else:
                raise Exception(
                    f"No results found for query: '{query}'. Use a less restrictive query."
                )
        if len(results["organic_results"]) == 0:
            date_filter_message = (
                f" with filter date={self.filter_date}"
                if self.filter_date is not None
                else ""
            )
            return f"No results found for '{query}'{date_filter_message}. Try with a more general query, or remove the date filter."

        web_snippets = {}
        if "organic_results" in results:
            for idx, page in enumerate(results["organic_results"]):
                redacted_version = {
                    "title": page["title"],
                    "url": page["link"],
                }

                if "date" in page:
                    redacted_version["date"] = page["date"]

                if "source" in page:
                    redacted_version["source"] = page["source"]

                if "snippet" in page:
                    redacted_version["snippet"] = page["snippet"]

                if "snippet_highlighted_words" in page:
                    redacted_version["snippet_highlighted_words"] = list(
                        set(page["snippet_highlighted_words"])
                    )

                web_snippets[idx] = redacted_version
        return web_snippets


    def snippet_filter(self, topic, snippet):
        """Calculate similarity score between topic and snippet

        Args:
            topic: The search topic
            snippet: The text snippet to compare against

        Returns:
            float: Similarity score between 0 and 100
        """
        prompt = SNIPPET_FILTER_PROMPT.format(
            topic=topic,
            snippet=snippet,
        )
        try:
            res = self.request_pool.completion(prompt)
            matches = re.findall(r"<SCORE>(\d+)</SCORE>", res)
            if not matches:
                raise ValueError("No valid SCORE found in response.")
            score = float(matches[-1])

            if score < 0 or score > 100:
                raise ValueError(f"Invalid similarity score: {score}")

            return score
        except Exception as e:
            logger.error(f"Error calculating similarity score: {e}")
            return 0.0

    def batch_web_search(self, queries: list, topic: str, top_n: int = 20) -> list:
        """
        Perform batch web search for multiple queries and return filtered results by relevance.

        Args:
            queries: List of search queries
            topic: Main topic for relevance filtering
            top_n: Number of most relevant URLs to return (default: 20)

        Returns:
            list: Filtered list of most relevant URLs
        """
        logger.info("Start to retrieve:")
        snippet_by_url = {}

        # Process each query
        for query in queries:
            if not query:
                logger.info("Skipping empty query")
                continue

            logger.info(f"==================\nThe query to be searched: {query}")

            try:
                web_snippets = self.web_search(query=query)
                if isinstance(web_snippets, str):
                    logger.info(web_snippets)
                    continue
            except Exception as e:
                logger.error(f"Error occurred while searching for query '{query}': {e}")
                continue

            # Process search results
            for info in web_snippets.values():
                url = info.get("url")
                if not url or url in snippet_by_url:
                    continue
                snippet_by_url[url] = {
                    "date": info.get("date"),
                    "snippet": info.get("snippet"),
                }

        if not snippet_by_url:
            logger.warning("No URLs were retrieved for the provided queries.")
            return []

        logger.info(
            f"Retrieved {len(snippet_by_url)} unique URLs, calculating similarities..."
        )

        # Use thread-based processing to avoid event loop conflicts
        def process_url_similarity(url_snippet_pair):
            """Process a single URL-snippet pair for similarity scoring"""
            url, snippet = url_snippet_pair
            try:
                if snippet:
                    score = self.snippet_filter(topic, snippet)
                    logger.info(f"Snippet similarity Score: {score}, Processed URL: {url}")
                    return (score, url)
                return (0, url)
            except Exception as e:
                logger.error(f"Error processing URL {url}: {e}")
                return (0, url)

        # Prepare URL-snippet pairs for processing
        url_snippet_pairs = [
            (url, info["snippet"])
            for url, info in snippet_by_url.items()
            if info["snippet"]
        ]

        # Use ThreadPoolExecutor for concurrent processing
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            scored_urls = list(executor.map(process_url_similarity, url_snippet_pairs))

        # Sort by score and get top N results
        scored_urls.sort(reverse=True, key=lambda x: x[0])
        filtered_urls = [url for _, url in scored_urls[:top_n]]

        logger.info(f"Returning top {len(filtered_urls)} most relevant URLs.")
        return filtered_urls

    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict]:
        return self.request_pool.get_conversation_history(limit)

    def clear_conversation_history(self):
        self.request_pool.clear_conversation_history()
        logger.info(f"Cleared conversation history for LLM_search model: {self.model}")

    def get_memory_statistics(self) -> Dict:
        return self.request_pool.get_memory_statistics()

    def export_conversation_history(self, output_file: str) -> bool:
        return self.request_pool.export_conversation_history(output_file)