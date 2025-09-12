import asyncio
import json
import logging
from typing import Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.data_structure import Survey
import traceback
import time
from args import parse_args

from src.decode.decode_pipeline import DecodePipeline

import gevent
gevent.monkey.patch_all()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentPipelineClient:
    """
    Manage connections to multiple Micro-Component Processing (MCP) servers, handling both connection establishment and termination.
    """
    
    def __init__(self):
        """
        Initializes all server session attributes to None and sets up 
        an AsyncExitStack for managing asynchronous context managers.
        
        Args:
            config_path: Path to the MCP configuration file (not implemented in current code)
        """
        self.digest_session = None
        self.skeleton_session = None
        self.group_session = None
        self.encode_session = None
        self.convolution_session = None
        self.basic_modules_session = None
        self.neurons_session = None
        self._exit_stack = AsyncExitStack()
        
    async def connect(self):
        try:          
            digest_params = StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "src.hidden.basic_modules.digest_module"],
                env={"PYTHONPATH": "/home/linsiyu/LLMxMapReduce-v3-fast/LLMxMapReduce/LLMxMapReduce_V3"}
            )
            
            skeleton_params = StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "src.hidden.basic_modules.skeleton_init_module"],
                env={"PYTHONPATH": "/home/linsiyu/LLMxMapReduce-v3-fast/LLMxMapReduce/LLMxMapReduce_V3"}
            )
            
            group_params = StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "src.hidden.basic_modules.group_module"],
                env={"PYTHONPATH": "/home/linsiyu/LLMxMapReduce-v3-fast/LLMxMapReduce/LLMxMapReduce_V3"}
            )

            skeleton_refine_params = StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "src.hidden.convolution_block.skeleton_module"],
                env={"PYTHONPATH": "/home/linsiyu/LLMxMapReduce-v3-fast/LLMxMapReduce/LLMxMapReduce_V3"}
            )
                            
            self.group_session = await self._exit_stack.enter_async_context(
                stdio_client(group_params)
            )

            self.skeleton_session = await self._exit_stack.enter_async_context(
                stdio_client(skeleton_params)
            )

            self.digest_session = await self._exit_stack.enter_async_context(
                stdio_client(digest_params)
            )

            self.skeleton_refine_session = await self._exit_stack.enter_async_context(
                stdio_client(skeleton_refine_params)
            )
        
            logger.info("Successfully connected to all MCP servers")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP servers: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self):
        await self._exit_stack.aclose()
        logger.info("Disconnected from all MCP servers")

    async def _execute_grouping(self, survey: Survey, config: Dict) -> Survey:
        logger.info("Executing references grouping...")
        try:

            read, write = self.group_session
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "group_papers",
                    {
                        "survey": survey.to_json(),
                        "config": config,
                    }
                )
            
            if result.content:
                json_result = result.content[0].text
                survey = Survey.from_json(json_result)
            
        except Exception as e:
            error_msg = traceback.format_exc()
            logger.error(f"Error in grouping: {e}\n\ntraceback: \n{error_msg}")

        return survey
    
    async def _skeleton_init(self, survey: Survey, config: Dict) -> Survey:
        logger.info("Executing skeleton initialization...")
        try:

            read, write = self.skeleton_session
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "skeleton_init",
                    {
                        "survey": survey.to_json(),
                        "config": config,
                    }
                )
            
            if result.content:
                json_result = result.content[0].text
                survey = Survey.from_json(json_result)
            
        except Exception as e:
            error_msg = traceback.format_exc()
            logger.error(f"Error in skeleton initialization: {e}\n\ntraceback: \n{error_msg}")
        
        return survey
    
    async def _digest(self, survey: Survey, config: Dict) -> Survey:
        logger.info("Executing digest generation...")
        try:

            read, write = self.digest_session
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "digest_generation",
                    {
                        "survey": survey.to_json(),
                        "config": config,
                    }
                )
            
            if result.content:
                json_result = result.content[0].text
                survey = Survey.from_json(json_result)

        except Exception as e:
            error_msg = traceback.format_exc()
            logger.error(f"Error in digest generation: {e}\n\ntraceback: \n{error_msg}")
        
        return survey
    
    async def _skeleton_refine(self, survey: Survey, config: Dict) -> Survey:
        logger.info("Executing skeleton refine...")
        try:

            read, write = self.skeleton_refine_session
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "skeleton_refine",
                    {
                        "survey": survey.to_json(),
                        "config": config,
                        "convolution_layer": "6",
                        "convolution_kernel_size": "3",
                        "convolution_result_num": "10",
                        "top_k": "6",
                        "self_refine_count": "0",
                        "self_refine_best_of": "3",
                    }
                )
            
            if result.content:
                json_result = result.content[0].text
                survey = Survey.from_json(json_result)
            
        except Exception as e:
            error_msg = traceback.format_exc()
            logger.error(f"Error in digest generation: {e}\n\ntraceback: \n{error_msg}")
        
        return survey

    async def pipeline_start(self, test_survey: Survey, config, output_file):

        await self.connect()

        try:
                
            group_start_time = time.time()
            survey = await self._execute_grouping(survey=test_survey, config=config)
            group_end_time = time.time()
            logger.info(f"Group Refenrence Finished: {survey.title}, Digest Count: {len(survey.digests)}\nTime consume: {group_end_time - group_start_time:.2f} seconds")

            skeleton_start_time = time.time()
            survey = await self._skeleton_init(survey=survey, config=config)
            skeleton_end_time = time.time()
            logger.info(f"Skeleton initialization done: Survey {survey.title}.\nTime consume: {skeleton_end_time - skeleton_start_time:.2f} seconds")

            digest_start_time = time.time()
            survey = await self._digest(survey=survey, config=config)
            digest_end_time = time.time()
            logger.info(f"Digest generation done: Survey {survey.title}.\nTime consume: {digest_end_time - digest_start_time:.2f} seconds")

            skeleton_refine_start_time = time.time()
            survey = await self._skeleton_refine(survey=survey, config=config)
            skeleton_refine_end_time = time.time()
            logger.info(f"Skeleton refine done: Survey {survey.title}.\nTime consume: {skeleton_refine_end_time - skeleton_refine_start_time:.2f} seconds")

            decode_pipeline = DecodePipeline(config=config['decode'], output_file=output_file)
            decode_pipeline.start()
            decode_pipeline.put(survey)
            while True:
                gevent.sleep(1)

        except Exception as e:
            logger.error(f"Failed: {e}\n\nTraceback:\n{traceback.format_exc()}")

async def main():

    args = parse_args()
    input_file = args.input_file
    config_path = args.config_file
    output_file_path = args.output_file
    
    async with AsyncExitStack() as stack:

        client = IntelligentPipelineClient()
        await stack.enter_async_context(client._exit_stack)

        await client.connect()

        with open(input_file, "r", encoding="utf-8") as f:
            json_data = json.load(f)
            if 'topic' in json_data:
                json_data['title'] = json_data['topic']
            if 'crawl_progress' in json_data:
                json_data['papers'] = json_data['crawl_progress']
                for i in range(len(json_data['papers'])):
                    json_data['papers'][i]['txt'] = json_data['papers'][i].get('content', '')
                    json_data['papers'][i]

            test_survey = Survey(json_data) if isinstance(json_data, dict) else json_data

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        await client.pipeline_start(test_survey, config, output_file=output_file_path)


if __name__ == "__main__":
    asyncio.run(main())