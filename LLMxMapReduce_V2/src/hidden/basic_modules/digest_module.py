import re
from typing import List
from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type
from request import RequestWrapper
from src.base_method.module import Neuron, Module
from src.base_method.data import Dataset
from src.data_structure import Digest, Survey
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)
from src.utils.process_str import (
    str2list,
    list2str,
    remove_illegal_bibkeys,
    parse_md_content,
)
import logging

logger = logging.getLogger(__name__)

from src.prompts import SINGLE_DIGEST_PROMPT


class DigestModule(Module):
    def __init__(self, config):
        super().__init__()
        self.module = SingleDigestModule(config)

    def forward(self, survey: Survey):
        outline = survey.skeleton
        dataset = Dataset([(digest, outline) for digest in survey.digests.values()])
        digest_list = self.module(dataset)
        survey.update_digests(digest_list)
        logger.info(f"All Digest Finished: Survey: {survey.title}")
        return survey


class SingleDigestModule(Module):
    def __init__(self, config):
        super().__init__()
        self.single_digest_neuron = SingleDigestNeuron(config["single"])
        self.merge_digest_neuron = MergeDigestNeuron(config["merge"])

    def forward(self, digest: Digest, outline):
        topic = digest.survey_title
        digest.suggestions = {}
        paper_infos = digest.get_paper_infos()
        for paper_info in paper_infos:
            paper_info["content"] = paper_info["origin_content"]
        bibkeys = list2str(digest.bibkeys)
        dataset = Dataset([(paper_info, outline, digest, Digest([], topic)) for paper_info in paper_infos])
        logger.info(f"Multiple Digest Generate Start, Count {len(dataset)} in survey {topic}: {bibkeys} ")
        
        digests = self.single_digest_neuron(
            dataset
        )
        digests = [digest for digest in digests if (digest is not None and digest is not Exception)]
        digest = self.merge_digest_neuron(digests, paper_infos, outline, digest)
        logger.info(f"Multiple Digest Generate Finished: {bibkeys} in survey {topic}")
        return digest


class SingleDigestNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = SINGLE_DIGEST_PROMPT
        self.request_pool = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )

    @retry(
        stop=stop_after_attempt(10),
        after=after_log(logger, logging.WARNING),
        retry=retry_if_exception_type(
            (
                BibkeyNotFoundError,
                StructureNotCorrespondingError,
                MdNotFoundError,
                IndexError,
                ValueError,
            )
        ),
    )
    def forward(self, paper_info, outline, digest, new_digest):
        outline_content = outline.all_skeleton(construction=True, with_index=True)
        outline_content = remove_illegal_bibkeys(
            outline_content, digest.bibkeys, raise_warning=False
        )
        outline_example = outline.all_skeleton(
            with_digest_placeholder=True, with_index=True
        )

        survey_title = outline.survey_title
        paper_bibkey = paper_info["bibkey"]
        paper_content = paper_info["content"]
        paper_content = paper_content.replace("#", "")
        prompt = SINGLE_DIGEST_PROMPT.format(
            survey_title=survey_title,
            paper_bibkey=f"{paper_bibkey}",
            paper_content=paper_content,
            survey_outline=outline_content,
            outline_example=outline_example,
        )
        result = ""
        try:
            # print(prompt)
            result = self.request_pool.completion(prompt)
            result = result.replace("['BIBKEY']", f"['{paper_bibkey}']")
            result = result.replace("[BIBKEY]", f"['{paper_bibkey}']")
            logger.info(f"Single Digest Generate Finished: {paper_bibkey}")

            
            new_digest.paper_infos = [paper_info]
            new_digest.parse_suggestion(result, paper_bibkey)
            new_digest = new_digest.parse_raw_digest(result, outline)
        except Exception as e:
            new_digest.failure_count += 1
            content_len = int(len(paper_content) * 0.5)
            paper_info["content"] = paper_content[:int(content_len)]
            if new_digest.failure_count >= 5:
                logger.warning(
                    f"Single Digest Generate Failed: {paper_bibkey}, Error: {e}, \nprompt: {prompt}, \nresult: {result}"
                )
            if new_digest.failure_count >=9:
                new_digest.parse_raw_digest(f"```markdown\n{outline.all_skeleton(with_index=True)}\n```", outline)
                logger.warning(
                    f"Single Digest Generate Failed, return empty: {paper_bibkey}, Error: {e}, \nprompt: {prompt}, \nresult: {result}"
                )
                return new_digest
            raise
        return new_digest


class MergeDigestNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.request_pool = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )

    @retry(
        stop=stop_after_attempt(15),
        after=after_log(logger, logging.WARNING),
        retry=retry_if_exception_type(
            (
                BibkeyNotFoundError,
                StructureNotCorrespondingError,
                MdNotFoundError,
                IndexError,
                ValueError,
            )
        ),
    )
    def forward(self, digests: List[Digest], paper_infos, outline, origin_digest):
        new_digest = Digest.from_multiple_digests(digests, outline)
        for i, section in enumerate(new_digest.root.all_section):
            section.description = ""
            descriptions = []
            for digest in digests:
                d_section = digest.root.all_section[i]
                if d_section.description:
                    descriptions.append(
                        f"Paper bibkey: [{''.join(digest.bibkeys)}]\nDigest: \n{d_section.description}"
                    )
            section.description = "--------------------\n".join(descriptions)
        return new_digest