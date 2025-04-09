import random
import re
from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type

from request import RequestWrapper
from src.base_method.module import Neuron, Module
from src.data_structure.content import ContentNode
from src.data_structure.digest import DigestNode
from src.utils.process_str import str2list, list2str, process_bibkeys
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)

import logging

logger = logging.getLogger(__name__)
from src.prompts import ORCHESTRA_PROMPT, SUMMARY_PROMPT

class OrchestraModule(Module):
    def __init__(self, config):
        super().__init__()
        self.orchestra_neuron = OrchestraNeuron(config['orchestra'])
        
    def forward(self, content: ContentNode):
        content = self.orchestra_neuron(content)
        content.is_content_qualified = True
        return content

class OrchestraNeuron(Neuron):
    def __init__(self, config):
        super().__init__()
        self.req_pool = RequestWrapper(
            model=config["model"],
            infer_type=config["infer_type"],
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
    def forward(self, content: ContentNode):
        try:
            title = content.survey_title
            section_title = content.title(with_index=False)
            outline = content.outline_node.get_skeleton(
                analysis=True, with_index=False
            ).strip()
            subcontents = content.subcontents(with_index=False)
            digests = content.digest_nodes
            bibkeys = list2str(content.digests.keys())
            digests = self._format_digests_clean_bibkey(
                digests, outline, content.failure_count
            )
            if content.is_leaf:
                prompt = ORCHESTRA_PROMPT
            else:
                prompt = SUMMARY_PROMPT
            prompt = prompt.format(
                title=title,
                outline=outline,
                digest=digests,
                bibkeys=bibkeys,
                section_title=section_title,
                subcontents=subcontents,
            )
            prompt = process_bibkeys(prompt)
            result = self.req_pool.completion(prompt)
            # logger.info(f"[DEBUG]Orchestra Node: {title}, result=\n{result}\n")
            if content.is_leaf:
                content.update_content(result, check_title=False)
            else:
                content.update_content(result)
            logger.info(f"Decode Orchestra Node: '{section_title}' from survey '{title}'")
            return content
        except Exception as e:
            logger.warning(f"Orchestra Node: {content.survey_title} failed, {e}, retrying...")
            content.failure_count += 1
            raise

    def _format_digests_for_orchestra(self, digests: dict[str, DigestNode]):
        digests = digests.items()
        random.shuffle(digests)
        return "\n\n".join([f"{digest.description}" for bibkey, digest in digests])

    def _format_digests_for_summary(self, digests: dict[str, DigestNode]):
        digests = digests.items()
        random.shuffle(digests)
        return "\n\n".join([f"{digest.description}" for bibkey, digest in digests])

    def _format_digests_clean_bibkey(
        self, digests: dict[str, DigestNode], outline: str, failure_count=0
    ):
        def split_digest(digests, outline: str):
            outline_bibkeys_reg = re.findall(r"\[([^\]]+)\]", outline)
            outline_bibkeys = set()
            for bibkey_str in outline_bibkeys_reg:
                bibkeys = str2list(bibkey_str)
                for bibkey in bibkeys:
                    outline_bibkeys.add(bibkey.strip())
            cited_digests = []
            not_cited_digests = []
            for bibkey, digest in digests.items():
                if any(b in outline_bibkeys for b in bibkey):
                    cited_digests.append(digest)
                else:
                    not_cited_digests.append(digest)
            return cited_digests, not_cited_digests

        cited_digests, not_cited_digests = split_digest(digests, outline)

        for _ in range(failure_count):
            not_cited_digests = random.sample(
                not_cited_digests, int(len(not_cited_digests) * 0.9)
            )

        new_digests = cited_digests + not_cited_digests
        random.shuffle(new_digests)
        digests_list = [f"{digest.description}" for digest in new_digests]
        digest_list_clean_bibkey = []
        for digest in digests_list:
            if len(digest) > 0:
                digest_list_clean_bibkey.append(digest)
        return "------------------\n".join(digest_list_clean_bibkey)

    def _format_digests(self, digests: dict[str, DigestNode]):
        digests = digests.items()
        random.shuffle(digests)
        return "\n\n".join(
            [
                f"**[{', '.join(bibkey)}]**: \n{process_bibkeys(digest.description)}"
                for bibkey, digest in digests
            ]
        )
