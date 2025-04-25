import os
import re
import asyncio
import traceback
from typing import Optional, Literal
import requests
import sys
import logging
from tenacity import retry, stop_after_attempt, before_log, retry_if_exception_type

sys.path.append("survey_writer")
from request import RequestWrapper
from prompts import (
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
        model: str = "claude-3-5-haiku-20241022",
        infer_type: str = "OpenAI",
        engine: Literal["google", "baidu", "bing"] = "google",
        count: int = 20,
        filter_date: Optional[str] = None,
        max_workers: int = 10,
    ):

        self.serpapi_key = os.getenv("SERP_API_KEY")
        self.model = model
        self.engine = engine
        self.count = count
        self.filter_date = filter_date
        self.max_workers = max_workers
        self.request_pool = RequestWrapper(model=model, infer_type=infer_type)

        if self.serpapi_key is None:
            raise ValueError("Missing SerpAPI key.")

    def _initialize_chat(self, topic: str, abstract: str = "") -> list:
        """Initialize chat messages for query generation"""
        if abstract:
            prompt = QUERY_EXPAND_PROMPT_WITH_ABSTRACT.format(
                topic=topic, abstract=abstract
            )
        else:
            prompt = QUERY_EXPAND_PROMPT_WITHOUT_ABSTRACT.format(topic=topic)

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
    ) -> list:
        """Get optimized search queries for a given topic

        Args:
            topic: Research topic
            description: Optional description/context of the topic

        Returns:
            list: List of optimized search queries
        """
        messages = self._initialize_chat(topic, description)
        queries = self._get_llm_response(messages)
        logger.info(f"Final count {len(queries)}:\n{queries}")
        return queries

    def web_search(
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
            params["num"] = self.count
            if self.filter_date is not None:
                params["tbs"] = f"cdr:1,cd_min:{self.filter_date}"

        elif self.engine == "baidu":
            params["rn"] = self.count
            if self.filter_date is not None:
                params["gpc"] = f"cdr:1,cd_min:{self.filter_date}"

        elif self.engine == "bing":
            params["count"] = self.count
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

        # Create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def process_similarities():
            queue = asyncio.Queue()

            total_url = len(snippet_by_url)
            # Producer: Add tasks to queue
            for url, info in snippet_by_url.items():
                if info["snippet"]:
                    await queue.put((url, info["snippet"]))

            async def consumer():
                scored_urls = []
                try:
                    while True:
                        try:
                            url, snippet = queue.get_nowait()
                            try:
                                if snippet:
                                    score = self.snippet_filter(topic, snippet)
                                    scored_urls.append((score, url))
                                    logger.info(
                                        f"Snippet similarity Score: {score}, rest {queue.qsize()}/{total_url}, Processed URL: {url}, "
                                    )
                            finally:
                                queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                except Exception as e:
                    logger.error(f"Error in consumer: {e}, {traceback.format_exc()}")
                return scored_urls

            # Start fixed number of consumer tasks
            consumers = [
                asyncio.create_task(consumer()) for _ in range(self.max_workers)
            ]

            await queue.join()

            # Collect all results
            results = await asyncio.gather(*consumers)
            all_scored_urls = []
            for result in results:
                all_scored_urls.extend(result)
            return all_scored_urls

        # Execute async processing
        scored_urls = loop.run_until_complete(process_similarities())

        # Sort by score and get top N results
        scored_urls.sort(reverse=True, key=lambda x: x[0])
        filtered_urls = [url for _, url in scored_urls[:top_n]]

        logger.info(f"Returning top {len(filtered_urls)} most relevant URLs.")
        return filtered_urls
