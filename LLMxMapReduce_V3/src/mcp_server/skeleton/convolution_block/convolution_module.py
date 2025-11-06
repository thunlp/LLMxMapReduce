import logging
import random
import numpy as np
import math
import json
from typing import List
from src.base_method.module import Module
from src.base_method.data import Dataset
from src.data_structure import Feedback, Skeleton, Survey
from src.mcp_server.skeleton.convolution_block.neurons import (
    ModifyOutlineNeuron,
    EvalOutlineNeuron,
    ConvolutionKernelNeuron,
)

import asyncio
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
import mcp.server.stdio
import json
import traceback

logger = logging.getLogger(__name__)
app = Server("convolution-module-processor")

@app.list_resources()
async def list_resources() -> List[Resource]:
    return [
        Resource(
            uri="convolution://processor/prompts",
            name="Convolution Processing Prompts",
            description="卷积处理的提示词模板",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "convolution://processor/prompts":
        prompts = {"Convolution Processing Prompts": ""}
        return json.dumps(prompts, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")
    
@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="convolution_layer_module",
            description="对综述大纲进行卷积处理",
            input_schema={
                "type": "object",
                "properties": {
                    "config": {
                        "type": "object",
                        "description": "卷积处理的配置参数，包括卷积层数、感受野、结果数量和top_k等",
                            },
                    "convolution_layer": {
                        "type": "integer",
                        "description": "卷积层数"
                    },
                    "receptive_field": {
                        "type": "integer",
                        "description": "感受野大小"
                    },
                    "result_num": {
                        "type": "integer",
                        "description": "每层卷积后保留的结果数量"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "每层卷积后保留的top_k个结果"
                    },
                    "survey": {
                        "type": "object",
                        "description": "待处理的综述对象，该工具的作用为对综述大纲进行卷积处理",
                    },
                    "utilise_results":{
                        "type": "object",
                        "description": "已利用的结果列表，包含已处理的反馈信息",
                    },
                    "origin_outline": {
                        "type": "object",
                        "description": "原始大纲"
                    }
                },
                "required": ["config", "convolution_layer", "receptive_field", "result_num", "top_k", "survey", "utilise_results", "origin_outline"]
            }
        )
    ]

@app.call_tool()
async def call_tool(
    tool_name: str, params_dict: str):
    if tool_name == "convolution_layer_module":
        config = params_dict["config"]
        convolution_layer = params_dict["convolution_layer"]
        receptive_field = params_dict["receptive_field"]
        result_num = params_dict["result_num"]
        top_k = params_dict["top_k"]

        survey = Survey.from_json(params_dict["survey"])
        utilise_results = [Feedback.from_json(f) for f in params_dict["utilise_results"]]
        origin_outline = Skeleton.from_json(params_dict["origin_outline"])
        try:
            convolution_layer_module = ConvolutionLayerModule(config["hidden"]["skeleton_refinement"]["convolution"], convolution_layer, receptive_field, result_num, top_k)
            convolution_result_dict = convolution_layer_module.forward(survey, utilise_results, origin_outline)
            return [TextContent(type="text", text=convolution_result_dict.to_json(), ensure_ascii=False, indent=2)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error calling tool {tool_name}: {e}\n\nTraceback\n{traceback.format_exc()}")]

class ConvolutionLayerModule(Module):
    def __init__(
        self,
        config,
        convolution_layer,
        receptive_field,
        result_num,
        top_k,
    ):
        super().__init__()
        self.convolution_layer = convolution_layer
        self.top_k = top_k
        self.receptive_field = receptive_field
        self.result_num = result_num

        self.convolution_module = ConvolutionModule(config)
        self.modify_neuron = ModifyOutlineNeuron(config["modify"], "residual")
        self.eval_neuron = EvalOutlineNeuron(config["eval"])

    def forward(
        self,
        survey: Survey,
        utilise_results: List[Feedback],
        origin_outline: str,
    ):
        bibkeys = survey.papers.keys()
        current_block_avg_scores = []
        origin_outline_score = self.eval_neuron(survey.title, origin_outline)
        old_grouped_suggestions = [[suggestion] for suggestion in utilise_results]
        conv_results_old = self.convolution_module(
            Dataset(
                [
                    (
                        survey.title,
                        origin_outline,
                        old_grouped_suggestion,
                        bibkeys,
                    )
                    for old_grouped_suggestion in old_grouped_suggestions
                ]
            )
        )
        utilise_results = [result[0] for result in conv_results_old]
        outlines = [result[1] for result in conv_results_old]
        scores = [result[2] for result in conv_results_old]
        avg_score = np.mean(scores)
        current_block_avg_scores.append(avg_score)
        logger.info(
            f"Survey {survey.title}, block cycle count {survey.block_cycle_count}, origin outline score: {origin_outline_score[0]}\nCurrent Layer Outline Scores: {scores}, Avg Score: {avg_score}, Max Score: {max(scores)}"
        )
        for layer_idx in range(self.convolution_layer):
            logger.info(
                f"Survey {survey.title}, block cycle count {survey.block_cycle_count}, Convolution Layer: {layer_idx} Start"
            )
            target_result_num = len(utilise_results) / self.receptive_field
            conv_results_new = self._convolution_forward(
                survey,
                origin_outline,
                utilise_results,
                bibkeys,
            )
            if target_result_num > self.result_num:
                # pooling
                conv_results = conv_results_old = conv_results_new
                utilise_results = [result[0] for result in conv_results]
                outlines = [result[1] for result in conv_results]
                scores = [result[2] for result in conv_results]
            else:
                conv_results = conv_results_old + conv_results_new
                conv_suggestions = [result[0] for result in conv_results]
                outlines = [result[1] for result in conv_results]
                scores = [result[2] for result in conv_results]

                utilise_results = self._prune_top_k(
                    conv_suggestions,
                    scores,
                    self.top_k,
                )
                conv_results_old = conv_results_new

            conv_new_scores = [result[2] for result in conv_results_new]
            avg_score = np.mean(conv_new_scores)
            current_block_avg_scores.append(avg_score)

            if target_result_num > self.result_num:
                logger.info(
                    f"Survey {survey.title}, block cycle count {survey.block_cycle_count}, Convolution Layer: {layer_idx} Pooling Finished\nCurrent Layer Outline Scores: {conv_new_scores}, Avg Score: {avg_score}, Max Score: {max(conv_new_scores)}"
                )
            else:
                logger.info(
                    f"Survey {survey.title}, block cycle count {survey.block_cycle_count}, Convolution Layer: {layer_idx} Convolution Finished\nCurrent Layer Outline Scores: {conv_new_scores}, Avg Score: {avg_score}, Max Score: {max(conv_new_scores)}"
                )

        new_outline = self._prune_top_k(outlines, scores, 1)[0]

        survey = survey.update_outline(
            "```markdown\n"
            + new_outline.all_skeleton(construction=True, analysis=True, with_index=True)
            + "\n```"
        )
        survey.skeleton.suggestion = new_outline.suggestion
        survey.skeleton.eval_score = new_outline.eval_score
        survey.skeleton.eval_detail = new_outline.eval_detail
        survey.block_avg_score.append(current_block_avg_scores)
        survey.conv_layer = self.convolution_layer
        survey.receptive_field = self.receptive_field
        survey.top_k = self.top_k
        survey.result_num = self.result_num
        return survey

    def _convolution_forward(self, survey, origin_outline, suggestions, bibkeys):
        old_grouped_suggestions = self._sample_suggestions(
            suggestions, self.receptive_field, self.result_num
        )
        logger.info(
            f"Survey {survey.title}, Sample Finished, suggestions count: {len(old_grouped_suggestions)}"
        )

        # suggestion, skeleton, score, score reason
        conv_results_new = self.convolution_module(
            Dataset(
                [
                    (
                        survey.title,
                        origin_outline,
                        old_grouped_suggestion,
                        bibkeys,
                    )
                    for old_grouped_suggestion in old_grouped_suggestions
                ]
            )
        )

        logger.info(
            f"Survey {survey.title}, Convolution Finished, suggestions count: {len(conv_results_new)}"
        )
        return conv_results_new

    def _sample_suggestions(
        self, suggestions, receptive_field, result_num
    ) -> List[List[Feedback]]:
        sampled_suggestions = []
        seen_combinations = set()
        all_possible_combinations = math.comb(len(suggestions), receptive_field)

        if result_num < len(suggestions) / receptive_field:
            logger.warning(
                f"Result num ({result_num}) is less than suggestions count ({len(suggestions)}) divided by receptive field ({receptive_field}), use no duplicate sampling"
            )
            np.random.shuffle(suggestions)
            sampled_suggestions = [
                suggestions[i : i + receptive_field]
                for i in range(0, len(suggestions), receptive_field)
            ]
        else:
            scores = [suggestion.score for suggestion in suggestions]
            scores = np.array(scores)
            scores /= scores.sum()

            available_indices = np.arange(len(suggestions))
            while len(sampled_suggestions) < result_num:
                if len(available_indices) < receptive_field:
                    sampled_indices = np.random.choice(
                        available_indices, size=len(available_indices), replace=True
                    )
                    logger.warning(
                        f"Sampled indices ({available_indices}) is less than receptive field({receptive_field}), use all available indices: {sampled_indices}"
                    )
                else:
                    sampled_indices = np.random.choice(
                        len(suggestions),
                        size=receptive_field,
                        replace=False,
                        p=scores,
                    )

                sampled_group = tuple(sorted(sampled_indices))
                if (
                    sampled_group not in seen_combinations
                    or len(seen_combinations) >= all_possible_combinations
                ):
                    seen_combinations.add(sampled_group)
                    sampled_suggestions.append(
                        [suggestions[i] for i in sampled_indices]
                    )

        return sampled_suggestions

    def _prune_top_k(self, results, scores, top_k):
        assert len(results) == len(scores)
        # 将score和outline降序排列，获取前top_k 个结果，同分项随机选择
        sorted_indices = np.argsort(scores)[::-1]
        sorted_suggestions = [results[i] for i in sorted_indices]
        sorted_scores = [scores[i] for i in sorted_indices]

        results = {}
        for outline, score in zip(sorted_suggestions, sorted_scores):
            if score not in results:
                results[score] = []
            results[score].append(outline)

        # 获取前top_k个结果
        result = []
        for score in sorted(results.keys(), reverse=True):
            group = results[score]
            if len(result) + len(group) <= top_k:
                result.extend(group)
            else:
                result.extend(random.sample(group, top_k - len(result)))
                break
        return result


class ConvolutionModule(Module):

    def __init__(self, config):
        super().__init__()
        self.conv_neuron = ConvolutionKernelNeuron(config["convolution_kernel"])
        self.modify_neuron = ModifyOutlineNeuron(config["modify"], "single_suggestion")
        self.eval_neuron = EvalOutlineNeuron(config["eval"])

    def forward(
        self,
        title,
        origin_outline: str,
        suggestions: List[Feedback],
        bibkeys: List[str],
    ) -> List[str]:
        new_suggestion = self.conv_neuron(title, origin_outline, suggestions, bibkeys)

        logger.info(f"Survey {title}, suggestion conv finished")

        new_outline = self.modify_neuron(
            title, [new_suggestion], origin_outline, bibkeys
        )
        logger.info(f"Survey {title}, outline modify Finished")
        scores_ret = self.eval_neuron(
            title,
            new_outline.all_skeleton(construction=True, analysis=True, with_index=True),
        )
        logger.info(f"Survey {title}, Eval Finished")
        new_suggestion.score = scores_ret[0]
        new_suggestion.eval_detail = scores_ret[1]

        # suggestion, skeleton, score, score reason
        new_outline.suggestion = new_suggestion.content
        new_outline.eval_score = scores_ret[0]
        new_outline.eval_detail = scores_ret[1]
        return new_suggestion, new_outline, scores_ret[0], scores_ret[1]
