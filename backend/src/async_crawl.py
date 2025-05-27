import json
import asyncio
import nest_asyncio
import time
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
import re
import sys

sys.path.append("survey_writer")
from request import RequestWrapper
from typing import List
from prompts import PAGE_REFINE_PROMPT, SIMILARITY_PROMPT
import logging
from src.database.mongo_manager import get_mongo_manager

logger = logging.getLogger(__name__)
# Enable nested event loops (suitable for Jupyter or IPython environments)
nest_asyncio.apply()

mongo_manager = get_mongo_manager()

class AsyncCrawler:
    # Configuration constants
    MAX_CONCURRENT_CRAWLS = 10
    MAX_CONCURRENT_PROCESSES = 10

    # Document processing constants
    DEFAULT_SIMILARITY_THRESHOLD = 80
    DEFAULT_MIN_LENGTH = 350
    DEFAULT_MAX_LENGTH = 20000

    def __init__(self, model="gemini-2.0-flash-thinking-exp-1219", infer_type="OpenAI"):
        """
        Initialize the AsyncCrawler.

        Args:
            model (str): Model identifier for text processing
            infer_type (str): Inference type, e.g., "OpenAI"
        """
        self.request_pool = RequestWrapper(model=model, infer_type=infer_type)

    async def run(
        self,
        topic: str,
        url_list: List[str],
        task_id: str,
        crawl_output_file_path: str = None,
        top_n: int = 80,
    ):
        """
        Asynchronously crawls a list of URLs, processes the crawled data, and saves the results.
        The process is split into four stages:
        1. URL crawling
        2. Content filtering and title generation
        3. Similarity scoring
        4. Result processing and saving

        Args:
            topic (str): The topic or theme associated with the URLs
            url_list (List[str]): A list of URLs to crawl
            task_id (str): The task ID for tracking
            crawl_output_file_path (str, optional): The file path where the final processed results will be saved (deprecated)
            top_n (int, optional): Maximum number of top results to save. Defaults to 80
        """
        process_start_time = time.time()
        stage_time = process_start_time
        logger.info(f"Starting crawling process for {len(url_list)} URLs, task_id={task_id}")

        # Stage 1: Concurrent URL crawling
        results = await self._crawl_urls(topic, url_list)
        logger.info(
            f"Stage 1 - Crawling completed in {time.time() - stage_time:.2f} seconds, with {len(results)} results"
        )
        stage_time = time.time()

        # Stage 2: Concurrent content filtering and title generation
        results = await self._process_filter_and_titles(results)
        logger.info(
            f"Stage 2 - Content filtering and title generation completed in {time.time() - stage_time:.2f} seconds, with {len(results)} results"
        )
        stage_time = time.time()

        # Stage 3: Concurrent similarity scoring
        results = await self._process_similarity_scores(results)
        logger.info(
            f"Stage 3 - Similarity scoring completed in {time.time() - stage_time:.2f} seconds, with {len(results)} results"
        )
        stage_time = time.time()

        # Stage 4: Result processing and saving
        self._process_results(results, task_id, topic, crawl_output_file_path, top_n=top_n)
        logger.info(
            f"Stage 4 - Results processing completed in {time.time() - stage_time:.2f} seconds, with {len(results)} results"
        )
        logger.info(
            f"Total processing completed in {time.time() - process_start_time:.2f} seconds"
        )

    async def _process_similarity_score(self, data):
        """
        Calculate similarity score for a single piece of data.
        """
        try:
            # Calculate similarity score using SIMILARITY_PROMPT
            prompt = SIMILARITY_PROMPT.format(
                topic=data["topic"], content=data["filtered"]
            )
            res = self.request_pool.completion(prompt)

            score = re.search(r"<SCORE>(\d+)</SCORE>", res)
            if not score:
                raise ValueError("Invalid similarity score format")

            data["similarity"] = int(score.group(1).strip())

        except Exception as e:
            logger.info(f"Failed to process similarity score: {e}")
            data["error"] = True
            data["similarity"] = -1
        return data

    async def _process_filter_and_title(self, data):
        """
        Process title generation and content filtering for a single piece of data.
        """
        try:
            # Generate title and filter content using PAGE_REFINE_PROMPT
            prompt = PAGE_REFINE_PROMPT.format(
                topic=data["topic"], raw_content=data["raw_content"]
            )
            res = self.request_pool.completion(prompt)
            title = re.search(r"<TITLE>(.*?)</TITLE>", res, re.DOTALL)
            content = re.search(r"<CONTENT>(.*?)</CONTENT>", res, re.DOTALL)

            if not title or not content:
                raise ValueError(f"Invalid response format, response: {res}")

            data["title"] = title.group(1).strip()
            data["filtered"] = content.group(1).strip()
        except Exception as e:
            logger.error(f"Failed to process filter and title: {e}")
            data["title"] = "Error in filtering"
            data["filtered"] = f"Error in filtering ({e})"
            data["error"] = True
        return data

    async def _process_similarity_scores(self, results: List[dict]) -> List[dict]:
        """
        Calculate similarity scores for filtered results using pure producer-consumer pattern.
        """
        input_queue = asyncio.Queue()
        output_queue = asyncio.Queue()
        total_items = len(results)

        # Producer: Add tasks to queue
        for data in results:
            await input_queue.put(data)

        async def consumer():
            while True:
                try:
                    data = input_queue.get_nowait()
                    try:
                        result = await self._process_similarity_score(data)
                        await output_queue.put(result)
                        logger.info(
                            f"Processed similarity score, remaining: {input_queue.qsize()}/{total_items}, URL: {data.get('url', 'N/A')}"
                        )
                    finally:
                        input_queue.task_done()
                except asyncio.QueueEmpty:
                    break

        # Create and start consumers
        consumers = [
            asyncio.create_task(consumer())
            for _ in range(self.MAX_CONCURRENT_PROCESSES)
        ]

        # Wait for all tasks to be processed
        await input_queue.join()

        # Collect results
        results = []
        while not output_queue.empty():
            data = await output_queue.get()
            if data["error"]:
                logger.error(f"Error in processing data, skip: {data}")
            else:
                results.append(data)

        return results

    async def _process_filter_and_titles(self, results: List[dict]) -> List[dict]:
        """
        Process title generation and content filtering using pure producer-consumer pattern.
        """
        input_queue = asyncio.Queue()
        output_queue = asyncio.Queue()
        total_items = len(results)

        # Producer: Add tasks to queue
        for data in results:
            await input_queue.put(data)

        async def consumer():
            while True:
                try:
                    data = input_queue.get_nowait()
                    try:
                        result = await self._process_filter_and_title(data)
                        await output_queue.put(result)
                        logger.info(
                            f"Title and filter processing completed, remaining: {input_queue.qsize()}/{total_items}, URL: {data.get('url', 'N/A')}"
                        )
                    finally:
                        input_queue.task_done()
                except asyncio.QueueEmpty:
                    break

        # Create and start consumers
        consumers = [
            asyncio.create_task(consumer())
            for _ in range(self.MAX_CONCURRENT_PROCESSES)
        ]

        # Wait for all tasks to be processed
        await input_queue.join()

        # Collect results
        results = []
        while not output_queue.empty():
            data = await output_queue.get()
            if data["error"]:
                logger.error(f"Error in processing data, skip: {data}")
            else:
                results.append(data)

        return results

    async def _crawl_urls(self, topic: str, url_list: List[str]) -> List[dict]:
        """
        Crawl URLs using pure producer-consumer pattern.
        """
        input_queue = asyncio.Queue()
        output_queue = asyncio.Queue()
        total_items = len(url_list)

        # Producer: Add URLs to queue
        for url in url_list:
            await input_queue.put((url, topic))

        async def consumer():
            while True:
                try:
                    url, topic = input_queue.get_nowait()
                    try:
                        result = await self._crawl_and_collect(url, topic)
                        await output_queue.put(result)
                        logger.info(
                            f"URL crawling completed, remaining: {input_queue.qsize()}/{total_items}, URL: {url}"
                        )
                    finally:
                        input_queue.task_done()
                except asyncio.QueueEmpty:
                    break

        # Create and start consumers
        consumers = [
            asyncio.create_task(consumer()) for _ in range(self.MAX_CONCURRENT_CRAWLS)
        ]

        # Wait for all tasks to be processed
        await input_queue.join()

        # Collect results
        results = []
        while not output_queue.empty():
            data = await output_queue.get()
            if data["error"]:
                logger.error(f"Error in processing data, skip: {data}")
            else:
                results.append(data)

        return results

    async def _crawl_and_collect(self, url: str, topic: str) -> dict:
        """
        Crawl a single URL and collect its content.

        Args:
            url (str): URL to crawl
            topic (str): Associated topic for the URL

        Returns:
            dict: Dictionary containing crawled data and metadata
        """
        try:
            raw_content = await self._simple_crawl(url)
            data = {
                "topic": topic,
                "url": url,
                "raw_content": raw_content,
                "error": False,
            }
        except Exception as e:
            logger.error(f"Crawling failed for URL={url}: {e}")
            data = {
                "topic": topic,
                "url": url,
                "raw_content": f"Error: Crawling failed({e})",
                "error": True,
            }

        return data

    async def _simple_crawl(self, url: str) -> str:
        """
        Perform a simple crawl of a URL using AsyncWebCrawler.

        Args:
            url (str): URL to crawl

        Returns:
            str: Raw markdown content from the webpage
        """
        crawler_run_config = CrawlerRunConfig(
            page_timeout=180000, cache_mode=CacheMode.BYPASS  # 180s timeout
        )

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=crawler_run_config)
            raw_markdown = result.markdown_v2.raw_markdown
            logger.info(f"Content length={len(raw_markdown)} for URL={url}")
            return raw_markdown

    def _process_results(
        self,
        results,
        task_id: str,
        topic: str,
        output_path: str = None,
        top_n=5,
        similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
        min_length=DEFAULT_MIN_LENGTH,
        max_length=DEFAULT_MAX_LENGTH,
    ):
        """
        Process crawling results and save to MongoDB.

        Args:
            results: Raw crawling results
            task_id: Task ID for tracking
            topic: The topic of the crawl
            output_path: Output file path (optional, for backward compatibility)
            top_n: Maximum number of documents to keep for each topic
            similarity_threshold: Similarity threshold
            min_length: Minimum document length
            max_length: Maximum document length
        """
        # Step 1: Process each paper data serially
        processed_data = []
        for data in results:
            try:
                # Build paper data
                paper_data = {
                    "title": data["title"],
                    "url": data["url"],
                    "txt": data["filtered"],
                    "similarity": data.get("similarity", 0),
                }
                processed_data.append((data["topic"], paper_data))
            except Exception as e:
                logger.error(f"Failed to process paper data: {e}")
                continue

        # Step 2: Organize data by topic
        topics = {}
        for topic_name, paper_data in processed_data:
            topics.setdefault(topic_name, []).append(paper_data)

        # Step 3: Save to MongoDB
        all_papers = []
        for topic_name, papers in topics.items():
            filtered_papers = self._filter_papers(
                papers,
                similarity_threshold,
                min_length,
                max_length,
                top_n,
            )
            all_papers.extend(filtered_papers)
        
        # 保存到 MongoDB
        if mongo_manager and mongo_manager.save_crawl_results(task_id, topic, all_papers):
            logger.info(f"Crawl results saved to MongoDB for task_id={task_id}, papers_count={len(all_papers)}")
        else:
            logger.error(f"Failed to save crawl results to MongoDB for task_id={task_id}")

        # Step 4: (可选) 如果提供了输出路径，同时保存到文件
        if output_path:
            try:
                with open(output_path, "w", encoding="utf-8") as outfile:
                    for topic_name, papers in topics.items():
                        filtered_papers = self._filter_papers(
                            papers,
                            similarity_threshold,
                            min_length,
                            max_length,
                            top_n,
                        )

                        output_data = {"title": topic_name, "papers": filtered_papers}
                        json.dump(output_data, outfile, ensure_ascii=False)
                        outfile.write("\n")

                logger.info(f"Processed data has also been saved to file: {output_path}")
            except Exception as e:
                logger.warning(f"Failed to save to file {output_path}: {e}, but data is saved in MongoDB")

    def _filter_papers(
        self,
        papers,
        similarity_threshold,
        min_length,
        max_length,
        top_n,
    ):
        """
        Filter papers based on criteria.

        Args:
            papers: List of papers to filter
            similarity_threshold: Minimum similarity score required
            min_length: Minimum document length
            max_length: Maximum document length
            minimal_length: Absolute minimum length allowed
            top_n: Maximum number of papers to return

        Returns:
            List of filtered papers
        """
        # Sort by similarity and length
        sorted_papers = sorted(papers, key=lambda x: (-x["similarity"], -len(x["txt"])))

        # Filter documents that are too short
        valid_length_papers = [
            p for p in sorted_papers if min_length <= len(p["txt"]) <= max_length
        ]

        # Filter documents by similarity and length requirements
        valid_similarity_papers = [
            p for p in valid_length_papers if p["similarity"] >= similarity_threshold
        ]

        # Add additional documents if needed to reach top_n
        if len(valid_similarity_papers) < top_n:
            remaining_papers = [
                p for p in valid_length_papers if p not in valid_similarity_papers
            ]
            valid_similarity_papers.extend(
                remaining_papers[: top_n - len(valid_similarity_papers)]
            )

        return valid_similarity_papers
