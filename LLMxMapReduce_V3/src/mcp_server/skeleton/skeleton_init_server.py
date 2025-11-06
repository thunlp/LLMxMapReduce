import random
import re
from typing import Dict, List
from request import RequestWrapper
from src.base_method.module import Neuron, Module
from src.base_method.data import Dataset
from src.utils.process_str import str2list, list2str
from src.data_structure import Skeleton, Survey, Digest
from src.exceptions import BibkeyNotFoundError, StructureNotCorrespondingError, MdNotFoundError
from src.prompts import CONCAT_OUTLINE_PROMPT, INIT_OUTLINE_PROMPT

from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type

import asyncio
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
import mcp.server.stdio
import json
import traceback
import os
import sys
import datetime

import logging
logger = logging.getLogger(__name__)

app = Server("skeleton-init-processor")
request_wrapper = None

log_dir = os.path.join(os.path.dirname(__file__), f'../../../output/{datetime.datetime.now().strftime("%Y%m%d")}/logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'skeleton_init_server.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

@app.list_resources()
async def list_resources() -> List[Resource]:
    return [
        Resource(
            uri="skeleton://processor/prompts",
            name="Skeleton Processing Prompts",
            description="Prompt templates for initializing survey outlines",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "skeleton://processor/prompts":
        prompts = {"skeleton_init": INIT_OUTLINE_PROMPT}
        return json.dumps(prompts, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")
    
@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="skeleton_init",
            description="Initialize survey outline",
            inputSchema={
                "type": "object",
                "properties": {
                    "survey": {
                        "type": "object",
                        "description": "The survey object to be processed. The function of this tool is to initially write an outline for the survey based on the survey title and grouped reference information",
                    },
                    "config": {"type": "object", "description": "Model configuration parameters required for outline initialization"},
                },
                "required": ["survey", "config"]
            }
        )
    ]

@app.call_tool()
async def call_tool(
    tool_name: str, params_dict: str):
    survey = Survey.from_json(params_dict["survey"])
    config = params_dict["config"]

    try:
        skeleton_init_module = SkeletonInitModule(config["hidden"]["skeleton"], batch_size=3) 
        skeleton_init_survey_dict = skeleton_init_module.forward(survey)
        return [TextContent(type="text", text=skeleton_init_survey_dict, ensure_ascii=False, indent=2)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error calling tool {tool_name}: {e}\n\nTraceback\n{traceback.format_exc()}")]

class SkeletonInitModule(Module):
    def __init__(self, config, batch_size):
        super().__init__()
        self.batch_size = batch_size
        self.outline_neuron = SingleSkeletonNeuron(config["single"])
        self.concat_neuron = ConcatSkeletonNeuron(config["concat"])

    def forward(self, survey: Survey):
        def split_digests(survey, step):
            items = list(survey.digests.items())
            random.shuffle(items)
            title = survey.title
            for i in range(0, len(items), step):
                yield title, dict(items[i : i + step])

        dataset = Dataset(split_digests(survey, self.batch_size))
        logger.info(f"Outline start: single Outline count {len(dataset)}")
        outlines = self.outline_neuron(dataset)
        if len(outlines) >= 1:
            survey = self.concat_neuron(survey, outlines)
        elif len(outlines) == 1:
            final_outline = outlines[0].raw_skeleton
            survey = survey.skeleton.parse_raw_skeleton(survey.title, final_outline)
        survey.skeleton_batch_size = self.batch_size
        logger.info(f"Outline finished: Survey {survey.title}.")
        return survey.to_json()


class SingleSkeletonNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = INIT_OUTLINE_PROMPT
        self.request_pool = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )

    @retry(
        stop=stop_after_attempt(5),
        after=after_log(logger, logging.WARNING),
        retry=retry_if_exception_type((BibkeyNotFoundError, StructureNotCorrespondingError, MdNotFoundError, ValueError)),
    )
    def forward(self, title, digests:Dict[str, Digest]):
        def format_abstract(digest_list):
            random.shuffle(digest_list)
            result = "\n---------------------\n".join([digest.abstract for digest in digest_list])
            return result

        def merge_frozensets(frozenset_list):
            result_set = set()
            for fs in frozenset_list:
                result_set.update(fs)
            return result_set

        digest_list = list(digests.values())
        format_abstracts = format_abstract(digest_list)
        bibkeys = [b for digest in digest_list for b in digest.bibkeys]
        bibkeys = list2str(bibkeys)
        prompt = self.prompt.format(
            title=title, abstracts=format_abstracts, bibkeys=bibkeys
        )
        new_raw_outline = self.request_pool.completion(prompt)
        new_outline = Skeleton(merge_frozensets(digests.keys()))
        new_outline.parse_raw_skeleton(title, new_raw_outline)
        logger.info(f"Single outline finished: Survey {title}.")
        return new_outline


class ConcatSkeletonNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = CONCAT_OUTLINE_PROMPT
        self.request = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )

    @retry(
        stop=stop_after_attempt(5),
        after=after_log(logger, logging.WARNING),
        retry=retry_if_exception_type((BibkeyNotFoundError, StructureNotCorrespondingError, MdNotFoundError, ValueError)),
    )
    def forward(self, survey, head_results):
        logger.info(f"Concat outline start: Survey {survey.title}.")
        bibkeys = list2str(survey.papers.keys())
        concat_results = self._concat_outlines(head_results)
        prompt = self.prompt.format(
            title=survey.title, outlines=concat_results, bibkeys=bibkeys
        )
        new_outline = self.request.completion(prompt)
        survey.skeleton.parse_raw_skeleton(survey.title, new_outline)
        logger.info(f"Concat outline finished: Survey {survey.title}.")
        return survey

    def _concat_outlines(self, outlines):
        result = []
        random.shuffle(outlines)
        for i, outline in enumerate(outlines):
            result.append(f"```markdown\n{outline.all_skeleton(construction=True, analysis=True, with_index=False)}\n```")
        result = "\n--------------------------\n".join(result)
        return result.strip()

async def main():
    logger.info("Starting Skeleton Initialization MCP Server...")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())