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
    # 配置常量
    MAX_CONCURRENT_CRAWLS = 10
    MAX_CONCURRENT_PROCESSES = 10

    # 文档处理相关的配置常量
    DEFAULT_SIMILARITY_THRESHOLD = 80
    DEFAULT_MIN_LENGTH = 1000
    DEFAULT_MAX_LENGTH = 20000
    DEFAULT_MINIMAL_LENGTH = 350

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
        """
        process_start_time = time.time()
        logger.info(f"Starting crawling process for {len(url_list)} URLs")

        # 第一阶段：并发爬取内容
        results = await self._crawl_urls(topic, url_list)
        logger.info(
            f"Crawling completed in {time.time() - process_start_time:.2f} seconds"
        )

        # 第二阶段：并发处理和相似度计算
        results = await self._process_contents(results)
        logger.info(
            f"Content processing completed in {time.time() - process_start_time:.2f} seconds"
        )

        # 第三阶段：结果处理和保存
        self.process_results(results, crawl_output_file_path, top_n=top_n)
        logger.info(
            f"Total processing completed in {time.time() - process_start_time:.2f} seconds"
        )

    async def _crawl_urls(self, topic: str, url_list: List[str]) -> List[dict]:
        """并发爬取所有URL的内容"""
        sem = asyncio.Semaphore(self.MAX_CONCURRENT_CRAWLS)
        tasks = [self.crawl_and_collect_with_sem(url, topic, sem) for url in url_list]
        return await asyncio.gather(*tasks)

    async def _process_contents(self, results: List[dict]) -> List[dict]:
        """并发处理爬取的内容并计算相似度"""
        sem_process = asyncio.Semaphore(self.MAX_CONCURRENT_PROCESSES)
        processing_tasks = [
            self.process_filtered_data(data, sem_process, drop_raw=False)
            for data in results
        ]
        return await asyncio.gather(*processing_tasks)

    async def crawl_and_collect_with_sem(self, url, topic, sem):
        async with sem:
            return await self.crawl_and_collect(url, topic)

    async def crawl_and_collect(self, url, topic):
        try:
            raw_content = await self.simple_crawl(url)
            if len(raw_content) < self.DEFAULT_MIN_LENGTH:
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
                    title, filtered_content, similarity_score = await asyncio.to_thread(
                        self.filter_data, data["topic"], data["raw_content"]
                    )
                    data["title"] = title
                    data["filtered"] = filtered_content
                    data["similarity"] = similarity_score
                except Exception as e:
                    logger.info(f"处理数据失败: {e}")
                    data['title'] = "Error in filtering"
                    data["filtered"] = f"Error in filtering ({e})"
                    data["similarity"] = -1  # 用于标记错误
            if drop_raw:
                data.pop("raw_content")
        return data

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APIError, ValueError)),
    )
    def filter_data(self, topic, raw_content):
        prompt = CRAWL_FILTER_PROMPT_WITH_TOPIC.format(
            topic=topic, raw_content=raw_content
        )
        logger.info(f"Filtering...")
        res = self.request_pool.completion(prompt)
        print(f"res={res}")
        title = re.search(r"<TITLE>(.*?)</TITLE>", res)
        if not title:
            raise ValueError("No valid TITLE found in response.")
        title = title.group(1).strip()
        
        content = re.search(r"<CONTENT>(.*?)</CONTENT>", res)
        if not content:
            raise ValueError("No valid CONTENT found in response.")
        content = content.group(1).strip()
        
        score = re.search(r"<SCORE>(\d+)</SCORE>", res)
        if not score:
            raise ValueError("No valid SCORE found in response.")
        score = int(score.group(1).strip())
        logger.info(f"Filtered. length={len(res)}")
        return title, content, score

    def process_results(
        self,
        results,
        output_path,
        top_n=5,
        similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
        min_length=DEFAULT_MIN_LENGTH,
        max_length=DEFAULT_MAX_LENGTH,
        minimal_length=DEFAULT_MINIMAL_LENGTH,
    ):
        """处理爬取结果并保存到文件 - 串行执行版本
        
        Args:
            results: 爬取的原始结果
            output_path: 输出文件路径
            top_n: 每个主题保留的最大文档数量
            similarity_threshold: 相似度阈值
            min_length: 最小文档长度
            max_length: 最大文档长度
            minimal_length: 允许的最小文档长度
        """
        # 第一步：串行处理每篇论文数据
        processed_data = []
        
        for data in results:
            if not data["error"]:
                try:
                    # 构建论文数据
                    paper_data = {
                        "title": data['title'],
                        "url": data["url"],
                        "abstract": data["filtered"],
                        "txt": data["filtered"],
                        "similarity": data.get("similarity", 0)
                    }
                    processed_data.append((data["topic"], paper_data))
                except Exception as e:
                    logger.error(f"处理论文数据失败: {e}")
                    continue
        
        # 第二步：按主题组织数据
        topics = {}
        for topic, paper_data in processed_data:
            topics.setdefault(topic, []).append(paper_data)
        
        # 第三步：写入文件
        with open(output_path, "w", encoding="utf-8") as outfile:
            for topic, papers in topics.items():
                filtered_papers = self._filter_papers(
                    papers,
                    similarity_threshold,
                    min_length,
                    max_length,
                    minimal_length,
                    top_n
                )
                
                output_data = {"title": topic, "papers": filtered_papers}
                json.dump(output_data, outfile, ensure_ascii=False)
                outfile.write("\n")
        
        logger.info(f"处理完成的数据已保存到 {output_path}")

    def _filter_papers(self, papers, similarity_threshold, min_length, max_length, minimal_length, top_n):
        """根据条件筛选论文"""
        # 按相似度和长度排序
        sorted_papers = sorted(
            papers, key=lambda x: (-x["similarity"], -len(x["txt"]))
        )

        # 过滤长度过短的文档
        valid_papers = [p for p in sorted_papers if len(p["txt"]) >= minimal_length]

        # 筛选满足相似度和长度要求的文档
        filtered_papers = [
            p for p in valid_papers
            if p["similarity"] >= similarity_threshold
            and min_length <= len(p["txt"]) <= max_length
        ]

        # 如果满足条件的文档不足，补充其他文档
        if len(filtered_papers) < top_n:
            remaining_papers = [p for p in valid_papers if p not in filtered_papers]
            filtered_papers.extend(remaining_papers[: top_n - len(filtered_papers)])

        return filtered_papers[:top_n]

    def extract_markdown_content(self, text):
        match = re.search(r"```markdown(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
