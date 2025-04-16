import re
from collections import defaultdict
from typing import Dict, List
from tenacity import retry, stop_after_attempt, after_log, retry_if_exception_type

from request import RequestWrapper
from src.base_method.module import Neuron, Module
from src.data_structure import Survey
from src.utils.process_str import proc_title_to_str
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)

import logging

logger = logging.getLogger(__name__)
from src.prompts import CHART_PROMPT


class FigureModule(Module):
    def __init__(self, config):
        super().__init__()
        self.figure_neuron = FigureNeuron(config["chart"])

    def forward(self, survey: Survey):
        logger.info(f"Start to process figure for {survey.title}")
        section_dict = survey.content.section_dict
        new_section_dict = {}
        for key, value in section_dict.items():
            key = proc_title_to_str(key)
            new_section_dict[key] = value
        
        title_list = section_dict.keys()
        chart_dict = self.figure_neuron(survey.content.all_content, title_list)

        for title, charts in chart_dict.items():
            title = proc_title_to_str(title)
            if title in new_section_dict:
                section_node = new_section_dict[title]
                for pos_sent, fig_title, img_type, code_content in charts:
                    safe_code_content = code_content.replace("\n", "\\n")
                    figure_link = f"<figure-link title='{fig_title}' type='{img_type}' content='{safe_code_content}'></figure-link>"
                    if pos_sent in section_node.content:
                        section_node.content = section_node.content.replace(pos_sent,
                                            "\n" + figure_link + "\n" + pos_sent, 1)
        logger.info(f"Finish processing figure for {survey.title}")
        return survey


class FigureNeuron(Neuron):
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
    def forward(self, content: str, title_list: List[str]) -> Dict[str, List[str]]:
        prompt = CHART_PROMPT.format(content=content, title_list=",".join(title_list))
        result = self.req_pool.completion(prompt)
        all_sections = defaultdict(list)
        
        pattern = r"Section Title:\s*(.+?)(?=\n)[\s\n]*Position Sentence:\s*(.+?)(?=\n)[\s\n]*Figure Title:\s*(.+?)(?=\n)[\s\n]*```(mermaid|markdown)\n([\s\S]+?)```"
        matches = re.finditer(pattern, result)

        for match in matches:
            section_title = match.group(1).strip()
            pos_sentence = match.group(2).strip()
            fig_title = match.group(3).strip()
            img_type = match.group(4).strip()
            code_content = match.group(5).strip()
            all_sections[section_title].append((pos_sentence, fig_title, img_type, code_content))
        return all_sections
