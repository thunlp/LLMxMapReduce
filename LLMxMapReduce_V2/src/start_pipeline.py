import os
import json
import logging
import gevent
from args import parse_args
import asyncio
from datetime import datetime

from async_d import Monitor, PipelineAnalyser
from async_d import Pipeline
from src.decode.decode_pipeline import DecodePipeline
from src.encode.encode_pipeline import EncodePipeline
from src.hidden.hidden_pipeline import HiddenPipeline
from src.LLM_search import LLM_search
from src.async_crawl import AsyncCrawler
from src.path_validator import get_path_validator

logger = logging.getLogger(__name__)


class EntirePipeline(Pipeline):
    def __init__(self, args):
        with open(args.config_file, "r") as f:
            self.config = json.load(f)

        self.parallel_num = args.parallel_num
        self.encode_pipeline = EncodePipeline(
            self.config["encode"], args.data_num
        )
        self.hidden_pipeline = HiddenPipeline(
            self.config["hidden"],
            args.output_each_block,
            args.digest_group_mode,
            args.skeleton_group_size,
            args.block_count,
            args.conv_layer,
            args.conv_kernel_width,
            args.conv_result_num,
            args.top_k,
            args.self_refine_count,
            args.self_refine_best_of,
            worker_num=self.parallel_num,
        )
        self.decode_pipeline = DecodePipeline(
            self.config["decode"], args.output_file, worker_num=self.parallel_num
        )

        all_nodes = [self.encode_pipeline, self.hidden_pipeline, self.decode_pipeline]

        super().__init__(
            all_nodes, head=self.encode_pipeline, tail=self.decode_pipeline
        )

    def _connect_nodes(self):
        self.encode_pipeline >> self.hidden_pipeline >> self.decode_pipeline


def start_pipeline(args):
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.WARNING)

    # start to write
    pipeline = EntirePipeline(args)

    pipeline_analyser = PipelineAnalyser()
    pipeline_analyser.register(pipeline)

    monitor = Monitor(report_interval=60)
    monitor.register(pipeline_analyser)
    monitor.start()

    pipeline.start()
    return pipeline


def main():
    args = parse_args()
    logger.info(f"Start pipeline with args: {args}")
    logger.info(f"Current language: {os.environ.get('PROMPT_LANGUAGE', 'en')}")
    if args.topic:
        logger.info("set --topic, start to auto retrieve pages from Internet")
        # get retrieve urls
        logger.info("---------Start to generate queries.-------------")
        retriever = LLM_search(model='gemini-2.0-flash-thinking-exp-01-21', infer_type="OpenAI", engine='google', each_query_result=10)
        queries = retriever.get_queries(topic=args.topic, description=args.description)
        logger.info("---------Start to search pages.-------------")
        url_list = retriever.batch_web_search(queries=queries, topic=args.topic, top_n=int(args.top_n * 1.2))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # get references
        path_validator = get_path_validator()
        crawl_output_path = path_validator.validate_output_path(
            topic=args.topic,
            timestamp=timestamp,
            suffix='crawl_result',
            extension='jsonl',
            base_dir='output'
        )

        crawler = AsyncCrawler(model="gemini-2.0-flash-thinking-exp-01-21", infer_type="OpenAI")
        asyncio.run(
            crawler.run(
                topic=args.topic,
                url_list=url_list,
                crawl_output_file_path=crawl_output_path,
                top_n=args.top_n
            )
        )
        print("---------References retrieve end.-------------")
        pipeline = start_pipeline(args)
        pipeline.put(crawl_output_path)
    elif args.input_file:
        logger.info("set --input_file, start to process the input file")
        pipeline = start_pipeline(args)
        pipeline.put(args.input_file)
    else:
        raise ValueError("Either --topic or --input_file should be set.")

    while True:
        gevent.sleep(5)


if __name__ == "__main__":
    main()