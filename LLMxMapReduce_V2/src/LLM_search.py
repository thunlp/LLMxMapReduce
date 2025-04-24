import os
import re
from typing import Optional, Literal
import requests
import sys
import logging
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_random_exponential, 
    before_log, 
    retry_if_exception_type
)
sys.path.append('survey_writer')
from request import RequestWrapper
import argparse
from pathlib import Path
from prompts import (
    SEARCH_SYSTEM_PROMPT_WITH_ABSTRACT, SEARCH_SYSTEM_PROMPT_WITHOUT_ABSTRACT, 
    SEARCH_USER_PROMPT, 
    QUERY_REFINE_STOP_FLAG, 
    USER_CHECK_PROMPT, 
    LLM_CHECK_PROMPT
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
        The specific LLM model to use for query decomposition and refinement. Defaults to 'claude-3-5-haiku-20241022'.

    engine : Literal['google', 'baidu', 'bing'], optional, default='google'
        The search engine to use for performing web searches. Options include 'google', 'baidu', 
        and 'bing'. Defaults to 'google'.

    user_refine : bool, optional, default=False
        If True, allows user interaction to refine the search queries manually. If False, the 
        refinement process is fully automated. Defaults to False.

    count (int): The number of search results to retrieve. 
        Google doesn't specify a clear upper limit, but setting a very large value may lead to poor performance. It's recommended to keep it below 100. 
        Baidu and Bing search engine support a maximum of 50 search results. Default is 10.
    filter_date (Optional[str]): An optional parameter to filter out search results before a certain date. 
        The date format should be 'dd/mm/yyyy', e.g., '01/01/2023' to filter out results before January 1st, 2023.
    """

    def __init__(
            self,
            model: str = 'claude-3-5-haiku-20241022',
            infer_type: str = "OpenAI",
            engine: Literal['google', 'baidu', 'bing'] = 'google', 
            count: int = 20,
            filter_date: Optional[str] = None,
            ):
        
        self.serpapi_key = os.getenv('SERP_API_KEY')
        self.model = model
        self.engine = engine
        self.count = count
        self.filter_date = filter_date
        self.request_pool = RequestWrapper(model=self.model, infer_type=infer_type)

        if self.serpapi_key is None:
            raise ValueError("Missing SerpAPI key.")

    def _initialize_chat(self, topic: str, abstract: str = "") -> list:
        """初始化聊天消息"""
        if abstract:
            system_prompt = SEARCH_SYSTEM_PROMPT_WITH_ABSTRACT.format(
                topic=topic, 
                abstract=abstract
            )
        else:
            system_prompt = SEARCH_SYSTEM_PROMPT_WITHOUT_ABSTRACT.format(
                topic=topic
            )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": SEARCH_USER_PROMPT},
        ]

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(QueryParseError),
        before=before_log(logger, logging.DEBUG)
    )
    def _get_llm_response(self, message) -> list:
        """Get response from LLM and parse queries

        Args:
            client: The LLM client instance
            messages: List of chat messages

        Returns:
            list: Parsed query list

        Raises:
            QueryParseError: If unable to parse queries from response
        """
        try:
            response = self.request_pool.completion(message)
            reg = r'```markdown\n([\s\S]*?)```'
            match = re.search(reg, response)
            if not match:
                raise QueryParseError("Unable to parse query list from response")
            return match.group(1).strip().split(";")
        except Exception as e:
            logger.error(f"Failed to parse queries: {e}, current response: {response}")
            raise QueryParseError(f"Query parsing failed: {e}")

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
        """Get optimized search queries

        Args:
            topic: Research topic
            abstract: Optional abstract text

        Returns:
            list: List of optimized search queries
        """
        messages = self._initialize_chat(topic, description)
        queries = self._get_llm_response(messages)
        logger.info(f'Final queries:\n{queries}\nQuery count:{len(queries)}')
        return queries

    def web_search(
            self,
            query: str,
            ):
        """
        Perform a network search for a single query.

        This function takes a single query as input in string format.
        It conducts a network search based on the given query and returns
        a dict containing search results. Each item in the dictionary
        represents a search result with keys such as 'title', 'url', 'date',
        'source', 'snippet', and 'snippet_highlighted_words'.

        Args:
            query (str): The search query as a string. 

        Returns:
            web_snippets (dict): A dictionary containing search results.
                Example structure:
                {
                    "0": {
                        "title": "Elon Musk: AI will surpass the sum of human intelligence in 2029, the development of AI either...",
                        "url": "https://finance.sina.com.cn/roll/2025-03-03/doc-inenkmnh6650208.shtml",
                        "date": "23 hours ago",
                        "source": "Sina Finance",
                        "snippet": "On March 1st, Elon Musk expressed his views on AI in a podcast. He predicted that AI intelligence will exceed the sum of human intelligence in 2029. AI may develop self - awareness. The impact on humans is 80% likely to be good, but 20% has the risk of extinction.",
                        "snippet_highlighted_words": ["Elon Musk"]
                    },
                    ...
                }
        """
        
        params = {
                "engine": self.engine,
                "q": query.lstrip('\"').rstrip('\"'),
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
                raise Exception(f"No results found for query: '{query}'. Use a less restrictive query.")
        if len(results["organic_results"]) == 0:
            date_filter_message = f" with filter date={self.filter_date}" if self.filter_date is not None else ""
            return f"No results found for '{query}'{date_filter_message}. Try with a more general query, or remove the date filter."

        web_snippets = {}
        if "organic_results" in results:
            for idx, page in enumerate(results["organic_results"]):
                redacted_version = {
                    'title': page['title'],
                    'url': page['link'],
                }

                if 'date' in page:
                    redacted_version['date'] = page['date']

                if 'source' in page:
                    redacted_version['source'] = page['source']

                if 'snippet' in page:
                    redacted_version['snippet'] = page['snippet']

                if 'snippet_highlighted_words' in page:
                    redacted_version['snippet_highlighted_words'] = list(set(page['snippet_highlighted_words']))

                web_snippets[idx] = redacted_version
        return web_snippets

    def batch_web_search(
            self,
            queries: list
            ):
        """
        Perform web searches in batch by looping through a list of queries.

        Args:
            queries (list): A list of search queries.

        Returns:
            retrieve_results (dict): The retrieve results dict, containing all the web_snippets dict for every query.
            urls (list): A list of retrieve urls from each web search.
        """
        print('Start to retrieve:')
        retrieve_results_with_queries = {} # Each query with its retrieved results
        url_list = []
        for query in queries:
            if not query:
                continue
            print('==================')
            print(f'The query to be searched: {query}')
            web_snippets = self.web_search(query=query)
            retrieve_results_with_queries[query] = web_snippets

            for idx in web_snippets:
                print(f'Retrieved result {idx}:\n{web_snippets[idx]}\n\n')
                url = web_snippets[idx]['url']
                if url not in url_list:
                    url_list.append(url)
                    
        
        return url_list
