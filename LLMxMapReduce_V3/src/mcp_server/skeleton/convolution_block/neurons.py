import logging
import re
import random

from copy import deepcopy
from typing import List
from request import RequestWrapper
from src.base_method.module import Neuron

from src.data_structure import Feedback, Skeleton, Digest
from src.utils.process_str import list2str, parse_md_content
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)
from src.prompts import (
    MODIFY_OUTLINE_PROMPT,
    OUTLINE_CONVOLUTION_PROMPT,
    OUTLINE_ENTROPY_PROMPT,
    DIGEST_FREE_PROMPT,
    RESIDUAL_MODIFY_OUTLINE_PROMPT
)
from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type


logger = logging.getLogger(__name__)


class FeedbackClusterNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = config.get("prompt", "")
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
                ValueError,
            )
        ),
    )
    def forward(self, title, digests, outline: Skeleton, usage):
        logger.info(
            f"Feedback Cluster start: Survey: {title}, Digests: {'; '.join([', '.join(digest.bibkeys) for digest in digests])}"
        )
        try:
            processed_digests = self.format_digests(digests, outline)
            bibkeys = [b for digest in digests for b in digest.bibkeys]
            bibkeys = list2str(bibkeys)
            origin_prompt = usage
            prompt = origin_prompt.format(
                title=title,
                digests=processed_digests,
                outline=outline.all_skeleton(
                    construction=True, analysis=True, with_index=True
                ),
                usage=usage,
                bibkeys=bibkeys,
            )
            suggestions = self.request_pool.completion(prompt)
            parsed_suggestions = parse_md_content(suggestions, label="suggestion")
            suggestion = Feedback(
                src_outline=outline.all_skeleton(
                    construction=True, analysis=True, with_index=True
                ),
                content=parsed_suggestions,
                digests=digests,
            )
        except Exception as e:
            logger.warning(f"Residual suggestion failed: {e}")
            raise

        logger.info(
            f"Feedback Cluster finished: Survey: {title}, Digests: {'; '.join([', '.join(digest.bibkeys) for digest in digests])}"
        )
        return suggestion

    def format_digests(self, digests, outline: Skeleton):
        def format_suggestions(suggestions: dict[str, str]):
            result = []
            for bibkey, suggestion in suggestions.items():
                result.append(f"Bibkey: {bibkey}\nSuggestion: \n{suggestion}\n")
            return "\n".join(result)

        formatted_digests = []
        random.shuffle(digests)
        new_digest = Digest.from_multiple_digests(digests, outline)
        return f"Digest Content: \n{new_digest.all_content(with_title=False)}\nFeedbacks: \n{format_suggestions(new_digest.suggestions)}"


class ConvolutionKernelNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = OUTLINE_CONVOLUTION_PROMPT
        self.request = RequestWrapper(
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
    def forward(
        self, survey_title, origin_outline, suggestions: List[Feedback], bibkeys
    ):
        def concat_suggestions(suggestions):
            random.shuffle(suggestions)
            result = "------------------------------\n".join(
                [
                    f"Suggestion Content: \n<CONTENT>\n{suggestion.content}\n</CONTENT>\n\nEvaluation: \n<EVALUATION>\n{suggestion.eval_detail}\n</EVALUATION>\n"
                    for i, suggestion in enumerate(suggestions)
                ]
            )
            return result

        if len(suggestions) == 1:
            return deepcopy(suggestions[0])

        concated_suggestions = concat_suggestions(suggestions)
        prompt = self.prompt.format(
            title=survey_title,
            outline=origin_outline,
            suggestions=concated_suggestions,
            bibkeys=list2str(bibkeys),
        )
        merge_suggestion = self.request.completion(prompt)
        logger.debug(
            f"Convolution Kernel Neuron finished, Prompt: \n{prompt}\nMerged Suggestion: \n{merge_suggestion}"
        )
        new_suggestion = parse_md_content(merge_suggestion, label="suggestion")
        new_digests = [
            digest for suggestion in suggestions for digest in suggestion.digests
        ]
        new_suggestion = Feedback(
            src_outline=origin_outline,
            content=new_suggestion,
            digests=new_digests,
        )
        return new_suggestion


class ModifyOutlineNeuron(Neuron):
    def __init__(self, config, modify_mode):
        super().__init__()
        self.modify_mode = modify_mode
        self.prompt = MODIFY_OUTLINE_PROMPT if modify_mode == "single_suggestion" else RESIDUAL_MODIFY_OUTLINE_PROMPT
        self.request = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )

    @retry(
        stop=stop_after_attempt(20),
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
    def forward(self, title, utilise_results, old_outline, bibkeys) -> Skeleton:
        concat_results = self._concat_suggestions(utilise_results)
        prompt = self.prompt.format(
            title=title,
            outlines=concat_results,
            old_outline=old_outline,
            bibkeys=list2str(bibkeys),
        )
        new_raw_outline = self.request.completion(prompt)
        new_outline = Skeleton(bibkeys)
        new_outline = new_outline.parse_raw_skeleton(title, new_raw_outline)
        logger.info(f"Modify Outline finished: Survey {title}")
        return new_outline

    def _concat_outlines(self, outlines):
        result = []
        for i, data in enumerate(outlines):
            outline, description = data
            result.append(
                f"**Think Perspective**: \n{description}\n**Outline Content**: \n{outline.all_skeleton(constrution=True, analysis=True)}\n\n"
            )
        result = "------------------------\n".join(result)
        return result

    def _concat_suggestions(self, suggestions: List[Feedback]):
        result = []
        for i, suggestion in enumerate(suggestions):
            result.append(f"Suggestions: \n{suggestion.content}\n")
        result = "------------------------\n".join(result)
        return result


class EvalOutlineNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = OUTLINE_ENTROPY_PROMPT
        self.request = RequestWrapper(
            model=config["model"], infer_type=config["infer_type"]
        )
        self.max_score = config["max_score"]

    @retry(
        stop=stop_after_attempt(15),
        after=after_log(logger, logging.WARNING),
        retry=retry_if_exception_type((IndexError, ValueError)),
    )
    def forward(self, title, outline) -> tuple[int, str]:
        def parse_score(raw_str):
            reg = re.compile(r"<SCORE>\s*(\d+\.\d+|\d+)\s*</SCORE>", re.DOTALL)
            score = reg.findall(raw_str)[0]
            score = float(score)
            if score > self.max_score:
                raise ValueError(
                    f"Score: {score} is larger than max score: {self.max_score}"
                )
            return score

        prompt = self.prompt.format(
            title=title,
            outline=outline,
        )
        result = self.request.completion(prompt)
        logger.debug(f"Eval Outline finished, Prompt: {prompt}\nResult: {result}")
        score = parse_score(result)
        return score, result


class SelfRefineNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.prompt = DIGEST_FREE_PROMPT
        self.request = RequestWrapper(
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
                ValueError,
            )
        ),
    )
    def forward(self, title, old_outline: str, eval_detail: str):
        prompt = self.prompt.format(
            title=title,
            outline=old_outline,
            eval_detail=eval_detail,
        )
        suggestions = self.request.completion(prompt)
        parsed_suggestions = parse_md_content(suggestions, label="suggestion")
        suggestion = Feedback(
            src_outline=old_outline,
            content=parsed_suggestions,
            digests=[],
        )
        return suggestion
