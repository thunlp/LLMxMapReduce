import logging
import random
from typing import List
from src.base_method.data import Dataset
from src.base_method.module import Module
from src.data_structure import Survey

from .convolution_module import ConvolutionLayerModule
from .refine_module import SelfRefineModule
from src.prompts import DIGEST_BASE_PROMPT
from src.hidden.convolution_block.neurons import (
    FeedbackClusterNeuron,
)
import asyncio
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
import mcp.server.stdio
import json
import traceback

app = Server("skeleton-refine-processor")

logger = logging.getLogger(__name__)

@app.list_resources()
async def list_resources() -> List[Resource]:
    return [
        Resource(
            uri="skeleton_refine://processor/prompts",
            name="Skeleton Refine Prompts",
            description="Skeleton refinement prompts",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "skeleton_refine://processor/prompts":
        prompts = {"skeleton_refine": DIGEST_BASE_PROMPT}
        return json.dumps(prompts, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")
    
@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="skeleton_refine",
            description="Skeleton refine tool for processing surveys and refining the survey skeleton using a convolution-like approach on the references.",
            input_schema={
                "type": "object",
                "properties": {
                    "survey": {
                        "type": "object",
                        "description": "The survey data structure.",
                    },
                    "config": {"type": "object", "description": "The model configuration parameters needed for summary generation."},
                    "convolution_layer": {"type": "object", "description": "The number of iterations when summarizing references using a convolution-like approach."},
                    "convolution_kernel_size": {"type":"object", "description": "The number of references processed in each iteration when summarizing references using a convolution-like approach."},
                    "convolution_result_num": {"type":"object", "description": "The number of results when summarizing references using a convolution-like approach."},
                    "top_k": {"type": "object","description": "The top_k results to keep after each convolution layer."},
                    "self_refine_count": {"type": "object", "description": "The number of self-refinements after the outline generation."},
                    "self_refine_best_of": {"type": "object", "description": "The number of samples to consider during self-refinement."},
                "required": ["survey", "config","convolution_layer", "convolution_kernel_size", "convolution_result_num", "top_k", "self_refine_count", "self_refine_best_of"]
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(
    tool_name: str, params_dict: str):
    
    if tool_name == "skeleton_refine":
        survey = Survey.from_json(params_dict["survey"])
        config = params_dict["config"]
        convolution_layer = int(params_dict["convolution_layer"])
        convolution_kernel_size = int(params_dict["convolution_kernel_size"])
        convolution_result_num = int(params_dict["convolution_result_num"])
        top_k = int(params_dict["top_k"])
        self_refine_count = int(params_dict["self_refine_count"])
        self_refine_best_of = int(params_dict["self_refine_best_of"])

        try:
            skeleton_refine_module = SkeletonRefineModule(
                config["hidden"]["skeleton_refinement"],
                convolution_layer=convolution_layer,
                receptive_field = convolution_kernel_size,
                result_num = convolution_result_num,
                top_k=top_k,
                self_refine_count=self_refine_count,
                self_refine_best_of=self_refine_best_of,)
            skeleton_survey_dict = skeleton_refine_module.forward(survey)
            return [TextContent(type="text", text=skeleton_survey_dict, ensure_ascii=False, indent=2)]
        
        except Exception as e:
            return [TextContent(type="text", text=f"Error calling tool {tool_name}: {e}\n\nTraceback\n{traceback.format_exc()}")]

class SkeletonRefineModule(Module):
    def __init__(
        self,
        configs,
        convolution_layer,
        receptive_field,
        result_num,
        top_k,
        self_refine_count,
        self_refine_best_of,
    ):
        super().__init__()
        self.feedback_cluster_neuron = FeedbackClusterNeuron(configs["cluster"])

        self.convolution_layer_module = ConvolutionLayerModule(
            configs["convolution"],
            convolution_layer,
            receptive_field,
            result_num,
            top_k,
        )

        self.self_refine_module = SelfRefineModule(
            configs["refine"], self_refine_count, self_refine_best_of
        )

    def forward(self, survey):
        logger.info(
            f"Skeleton refine module start: Survey {survey.title} block cycle count: {survey.block_cycle_count}"
        )
        skeleton = survey.skeleton
        title = survey.title
        digests = survey.digests.values()

        dataset = Dataset(
            [
                (
                    title,
                    [digest_group],
                    skeleton,
                    DIGEST_BASE_PROMPT,
                )
                for digest_group in digests
            ]
        )

        logger.info(
            f"Feedback Cluster start: Count {len(dataset)} Survey: {title}, Digest Group Count: {len(dataset)}"
        )
        utilise_results = self.feedback_cluster_neuron(dataset)
        logger.info(
            f"Feedback Cluster finished: Survey: {title}, Digest Group Count: {len(dataset)}"
        )

        survey = self.convolution_layer_module(
            survey,
            utilise_results,
            skeleton.all_skeleton(construction=True, analysis=True, with_index=True),
        )
        logger.info(f"Convolution layer module finished: Survey {survey.title}")

        survey = self.self_refine_module(survey)
        logger.info(f"Self-refine module finished: Survey {survey.title}")

        survey.block_cycle_count += 1
        logger.info(
            f"Skeleton-refine module finished: Survey {survey.title} block cycle count: {survey.block_cycle_count}"
        )
        return survey.to_json()

    def merge_results_from_one_description(self, utilise_results):
        result_dict = {}
        for result, description in utilise_results:
            if description not in result_dict:
                result_dict[description] = []
            result_dict[description].append(result)
        for description, results in result_dict.items():
            random.shuffle(results)
            result_dict[description] = "/n".join(results)
        result_list = [
            (result, description) for description, result in result_dict.items()
        ]
        random.shuffle(result_list)
        return result_list

async def main():
    logger.info("Starting Skeleton Refine Processor MCP Server...")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())