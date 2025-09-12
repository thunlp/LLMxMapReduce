import os
import logging
from args import parse_args
import asyncio
from datetime import datetime

from src.LLM_search import LLM_search
from src.async_crawl import AsyncCrawler

logger = logging.getLogger(__name__)


def main():
    args = parse_args()
    logger.info(f"Start pipeline with args: {args}")

    # if args.topic:
    logger.info("set --topic, start to auto retrieve pages from Internet")
    # get retrieve urls
    logger.info("---------Start to generate queries.-------------")
    retriever = LLM_search()
    queries = retriever.get_queries(topic=args.topic, description=args.description)
    logger.info("---------Start to search pages.-------------")
    url_list = retriever.batch_web_search(queries=queries)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # get references
    crawl_output_path = f"output/{args.topic}_{timestamp}_crawl_result.jsonl"
    if not os.path.exists(os.path.dirname(crawl_output_path)):
        os.mkdir(os.path.dirname(crawl_output_path))

    crawler = AsyncCrawler(model="gemini-2.0-flash-thinking-exp-1219")
    asyncio.run(
        crawler.run(
            topic=args.topic,
            url_list=url_list,
            crawl_output_file_path=crawl_output_path,
            top_n=args.top_n
        )
    )
    print("---------References retrieve end.-------------")


if __name__ == "__main__":
    main()
