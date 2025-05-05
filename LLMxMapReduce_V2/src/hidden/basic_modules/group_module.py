import re
from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type

import random
from typing import List
from request import RequestWrapper
from src.base_method.module import Neuron, Module
from src.data_structure import Digest, Survey
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)
from src.utils.process_str import list2str,str2list
from src.prompts import GROUP_PROMPT
import logging

logger = logging.getLogger(__name__)


class GroupModule(Module):
    def __init__(self, config, mode, digest_batch):
        super().__init__()
        self.mode = mode
        self.digest_batch = digest_batch
        self.neuron = GroupNeuron(config["neuron"])

    def forward(self, survey: Survey):
        papers = list(survey.papers.values())
        if self.mode == "random":
            papers = self._random_group_papers(papers, self.digest_batch)
        elif self.mode == "llm":
            papers = self._llm_group_papers(papers, self.digest_batch, survey.title)

        for paper_batch in papers:
            digest = Digest(paper_batch, survey.title)
            bibkeys = digest.bibkeys
            survey.digests[bibkeys] = digest

        survey.digest_batch_size = self.digest_batch
        logger.info(f"Group Survey Finished: {survey.title}, Digest Count: {len(survey.digests)}")
        return survey

    def _random_group_papers(self, papers, step):
        random.shuffle(papers)
        for i in range(0, len(papers), step):
            yield papers[i : i + step]

    def _sequential_group_papers(self, papers, step):
        for i in range(0, len(papers), step):
            yield papers[i : i + step]

    def _llm_group_papers(self, papers, step, survey_title):

        def regroup_result(result, rest_bibkeys, batch_size):
            final_result = []
            remaining_groups = []

            # Step 1: Split groups larger than batch_size
            for group in result:
                while len(group) >= batch_size:
                    final_result.append(group[:batch_size])
                    group = group[batch_size:]
                if group:
                    remaining_groups.append(group)

            # Step 2: Sort remaining_groups by length in descending order
            remaining_groups.sort(key=len, reverse=True)

            # Step 3: Combine groups to make their length equal to batch_size
            combined_groups = []
            while len(remaining_groups) > 1:
                group1 = remaining_groups.pop(0)
                for i in range(len(remaining_groups) - 1, -1, -1):
                    group2 = remaining_groups[i]
                    if len(group1) + len(group2) == batch_size:
                        final_result.append(group1 + group2)
                        remaining_groups.pop(i)
                        break
                else:
                    combined_groups.append(group1)

            # Step 4: Add remaining groups from rest_bibkeys
            for group in combined_groups:
                while len(group) < batch_size and rest_bibkeys:
                    group.append(rest_bibkeys.pop())
                final_result.append(group)

            # Step 5: Combine remaining rest_bibkeys into groups of batch_size
            rest_bibkeys = list(rest_bibkeys)
            random.shuffle(rest_bibkeys)
            for i in range(0, len(rest_bibkeys), batch_size):
                final_result.append(rest_bibkeys[i : i + batch_size])

            return final_result

        papers_info = [(paper["title"], paper["bibkey"]) for paper in papers]
        result = self.neuron.forward(papers_info, survey_title)
        parsed_result, rest_bibkeys = self._parse_group_result(
            result, [bibkey for _, bibkey in papers_info]
        )
        grouped_result = regroup_result(parsed_result, rest_bibkeys, step)
        for group in grouped_result:
            yield [paper for paper in papers if paper["bibkey"] in group]
        return

    def _parse_group_result(self, raw_result, bibkeys):
        result = []
        references_reg = re.compile(r"\[(.*?)\]")
        paper_groups = references_reg.findall(raw_result)
        for group in paper_groups:
            group = str2list(group)
            result.append(group)

        splited_bibkeys = [b for group in result for b in group]
        if hallucinate_bibkeys := set(splited_bibkeys) - set(bibkeys):
            result = [
                [b for b in group if b not in hallucinate_bibkeys] for group in result
            ]
        rest_bibkeys = set(bibkeys) - set(splited_bibkeys)

        return result, rest_bibkeys


class GroupNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = GROUP_PROMPT
        self.request_pool = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )

    @retry(
        stop=stop_after_attempt(5),
        after=after_log(logger, logging.WARNING),
        retry=retry_if_exception_type(
            (
                BibkeyNotFoundError,
                StructureNotCorrespondingError,
                MdNotFoundError,
                ValueError,
            )
        ),
    )
    def forward(self, papers_info, survey_title) -> List[List[str]]:
        def format_papers_info(papers_info):
            random.shuffle(papers_info)
            return "\n".join(
                [
                    f"Title: \"{title}\" Bibkey: '{bibkey}'"
                    for title, bibkey in papers_info
                ]
            )

        bibkeys = [bibkey for _, bibkey in papers_info]
        bibkeys = list2str(bibkeys)
        papers_info_str = format_papers_info(papers_info)
        prompt = self.prompt.format(
            survey_title=survey_title,
            titles=papers_info_str,
            bibkeys=bibkeys,
        )
        result = self.request_pool.completion(prompt)
        logger.info(f"Group Generate Finished: {survey_title}")
        return result
