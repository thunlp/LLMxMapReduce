import json
import asyncio
import nest_asyncio
import time
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)
from openai import InternalServerError, RateLimitError, APIError
import re
import sys

sys.path.append("survey_writer")
from request import RequestWrapper
from typing import List
from prompts import (
    CRAWL_FILTER_PROMPT_WITH_TOPIC,
    SIMILARITY_PROMPT,
    GENERATE_TITLE_PROMPT,
)
import logging

logger = logging.getLogger(__name__)
# Enable nested event loops (suitable for Jupyter or IPython environments).
nest_asyncio.apply()


class AsyncCrawler:
    def __init__(self, model="gemini-2.0-flash-thinking-exp-1219"):
        self.request_pool = RequestWrapper(model=model)

    async def run(
        self,
        topic: str,
        url_list: List[str],
        crawl_output_file_path: str,
        top_n: int = 80,
    ):
        """
        Asynchronously crawls a list of URLs, processes the crawled data, and saves the results.

        Args:
            topic (str): The topic or theme associated with the URLs. This is used for filtering and similarity scoring.
            url_list (List[str]): A list of URLs to crawl. Each URL will be processed asynchronously.
            crawl_output_file_path (str): The file path where the final processed results will be saved, which must be ended with '.jsonl'.
            top_n (int, optional): The maximum number of top results to save based on similarity and content length.
                                Defaults to 80.

        Workflow:
            1. Crawls all URLs in `url_list` concurrently, limiting the number of simultaneous requests using a semaphore.
            2. Filters the crawled content and calculates similarity scores for each URL's content against the `topic`.
            3. Saves the processed results to the specified `crawl_output_file_path`, keeping only the top `top_n` results.

        Notes:
            - The method uses asyncio for concurrent execution, with semaphores to limit resource usage.
            - The `process_filtered_data` method is responsible for filtering and similarity scoring.
            - The final results are sorted by similarity and content length, and only the top `top_n` entries are saved.
        """

        start_time = time.time()
        logger.info(f"Total {len(url_list)} urls to crawl.")

        # Limit the number of concurrent crawling tasks.
        start_time = time.time()
        sem = asyncio.Semaphore(10)
        tasks = [self.crawl_and_collect_with_sem(url, topic, sem) for url in url_list]
        results = await asyncio.gather(*tasks)
        logger.info(
            f"Crawling finished. Time spent {time.time() - start_time:.2f} seconds."
        )

        # Limit concurrent filter_data and get_similarity tasks.
        sem_process = asyncio.Semaphore(10)  # Limit concurrent API calls.
        processing_tasks = [
            self.process_filtered_data(data, sem_process, drop_raw=False)
            for data in results
        ]
        results = await asyncio.gather(*processing_tasks)
        logger.info(
            f"Filtering and similarity processing completed. Time spent {time.time() - start_time:.2f} seconds."
        )

        await self.process_results(results, crawl_output_file_path, top_n)
        logger.info(
            f"Format input data completed. Time spent {time.time() - start_time:.2f} seconds."
        )

        # 定义一个包装函数，用于在 semaphore 限制下运行任务

    async def crawl_and_collect_with_sem(self, url, topic, sem):
        async with sem:
            return await self.crawl_and_collect(url, topic)

    async def crawl_and_collect(self, url, topic):
        try:
            raw_content = await self.simple_crawl(url)
            if len(raw_content) < 500:
                logger.info(
                    f"for url={url}, content length is too short: {len(raw_content)}"
                )
                error_flag = True
            else:
                error_flag = False
            data = {
                "topic": topic,
                "url": url,
                "raw_content": raw_content,
                "error": error_flag,
            }
        except Exception as e:
            data = {
                "topic": topic,
                "url": url,
                "raw_content": f"Error: 爬取失败({e})",
                "error": True,
            }

        return data

    async def simple_crawl(self, url):
        crawler_run_config = CrawlerRunConfig(
            page_timeout=180000, cache_mode=CacheMode.BYPASS  # 180s limit
        )

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=crawler_run_config)
            raw_markdown = result.markdown_v2.raw_markdown
            # logger.info(f"First 500 chars:\n{raw_markdown[:500]}")
            logger.info(f"raw_content_length={len(raw_markdown)}")
            return raw_markdown

    async def process_filtered_data(self, data, sem, drop_raw=False):
        """对爬取的网页数据进行过滤和相似度计算"""
        async with sem:
            if not data["error"]:
                try:
                    # 过滤正文
                    filtered_content = await asyncio.to_thread(
                        self.filter_data, data["topic"], data["raw_content"]
                    )
                    data["filtered"] = filtered_content

                    # 计算相似度
                    similarity_score = await asyncio.to_thread(
                        self.get_similarity, data["topic"], filtered_content
                    )
                    data["similarity"] = similarity_score
                except Exception as e:
                    logger.info(f"处理数据失败: {e}")
                    data["filtered"] = f"Error in filtering ({e})"
                    data["similarity"] = -1  # 用于标记错误
            if drop_raw:
                data.pop("raw_content")
        return data

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APIError)),
    )
    def filter_data(self, topic, raw_content):
        prompt = CRAWL_FILTER_PROMPT_WITH_TOPIC.format(
            topic=topic, raw_content=raw_content
        )
        logger.info(f"Filtering...")
        res = self.request_pool.completion(prompt)
        logger.info(f"Filtered. length={len(res)}")
        return res

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APIError)),
    )
    def get_similarity(self, topic, content):
        prompt = SIMILARITY_PROMPT.format(topic=topic, content=content)
        logger.info(f"Calculating similarity...")
        res = self.request_pool.completion(prompt)
        logger.info(f"Calculated similarity. res={res}")
        try:
            matches = re.findall(r"<SCORE>(\d+)</SCORE>", res)  # 获取所有匹配项
            if not matches:
                raise ValueError("No valid SCORE found in response.")
            score = float(matches[-1])  # 选取最后一个匹配的数值
        except Exception as e:
            logger.info(f"Error parsing similarity score: {e}, res = {res}")
            raise e

        if score < 0 or score > 100:
            raise ValueError(f"Invalid similarity score: {score}")
        logger.info(f"Similarity calculated. score={score}")
        return score

    async def process_results(
        self,
        results,
        output_path,
        top_n=5,
        similarity_threshold=80,
        min_length=1000,
        max_length=20000,
        minimal_length=350,
    ):
        title_set = set()
        lock = asyncio.Lock()
        tasks = [
            self.process_paper(data, title_set, lock)
            for data in results
            if not data["error"]
        ]
        processed = await asyncio.gather(*tasks)

        topics = {}
        for topic, paper_data in processed:
            topics.setdefault(topic, []).append(paper_data)

        with open(output_path, "w", encoding="utf-8") as outfile:
            for topic, papers in topics.items():
                # **按照 similarity 降序排序，同分则按 txt 长度降序**
                sorted_papers = sorted(
                    papers, key=lambda x: (-x["similarity"], -len(x["txt"]))
                )

                # **首先过滤掉长度小于 minimal_length 的条目**
                valid_papers = [
                    p for p in sorted_papers if len(p["txt"]) >= minimal_length
                ]

                # **优先筛选满足 similarity 和长度阈值的数据**
                filtered_papers = [
                    p
                    for p in valid_papers
                    if p["similarity"] >= similarity_threshold
                    and min_length <= len(p["txt"]) <= max_length
                ]

                # **如果满足阈值的数据不足 top_n，填充剩余数据**
                if len(filtered_papers) < top_n:
                    remaining_papers = [
                        p for p in valid_papers if p not in filtered_papers
                    ]
                    filtered_papers.extend(
                        remaining_papers[: top_n - len(filtered_papers)]
                    )

                # **最终只保留 top_n 条**
                filtered_papers = filtered_papers[:top_n]

                output_data = {"title": topic, "papers": filtered_papers}
                json.dump(output_data, outfile, ensure_ascii=False)
                outfile.write("\n")
        logger.info(f"Processed papers 数据已保存到 {output_path}")

    async def process_paper(self, data, title_set, lock):
        # 异步调用同步的 generate_title
        title = await self.generate_title(data["filtered"], title_set, lock)
        paper_data = {
            "title": title,
            "url": data["url"],
            "abstract": data["filtered"],
            "txt": data["filtered"],
            "similarity": data.get("similarity", 0)
        }
        return data["topic"], paper_data

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type((ValueError)),
    )
    async def generate_title(self, text, title_set, lock: asyncio.Lock):
        """Generate a unique title for the text content
        
        Args:
            text: Content to generate title from
            title_set: Set of existing titles
            lock: Asyncio lock for thread safety
        
        Returns:
            str: Generated unique title
        """
        prompt = GENERATE_TITLE_PROMPT.format(text=text[:1000])
        logger.info("Sending text for generating title...")

        title = await asyncio.to_thread(self.request_pool.completion, prompt)
        logger.info(f"Received title: {title}")
        
        title = self.extract_markdown_content(title)
        if not title:
            raise ValueError("No title in markdown block! Retrying...")
        
        async with lock:  # 使用异步上下文管理器
            if title in title_set:
                raise ValueError("Title already exists! Retrying...")
            title_set.add(title)
        
        return title

    def extract_markdown_content(self, text):
        match = re.search(r"```markdown(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
