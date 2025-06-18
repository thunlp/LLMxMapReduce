import random
import re
from typing import Dict
from request import RequestWrapper
from src.base_method.module import Neuron, Module
from src.base_method.data import Dataset
from src.utils.process_str import str2list, list2str
from src.data_structure import Skeleton, Survey, Digest
from src.exceptions import BibkeyNotFoundError, StructureNotCorrespondingError, MdNotFoundError
from src.prompts import CONCAT_OUTLINE_PROMPT, INIT_OUTLINE_PROMPT

from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type
import logging
logger = logging.getLogger(__name__)


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
        survey = self.concat_neuron(survey, outlines)
        survey.skeleton_batch_size = self.batch_size
        logger.info(f"Outline finished: Survey {survey.title}.")
        return survey


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
