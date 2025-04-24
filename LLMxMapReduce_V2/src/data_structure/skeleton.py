import re
import traceback
from typing import Dict
from .digest import Digest
from .multi_key_dict import MultiKeyDict
from .treenode import TreeNode
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)
from ..utils.process_str import parse_md_content, remove_illegal_bibkeys, get_section_title
from src.logger import logger, logging


class SkeletonNode(TreeNode):
    def __init__(self, title):
        super().__init__()
        self.title = title
        self.description = ""
        self.construction = ""
        self.analysis = ""
        
        self.block_cycle_count = 0
        self.digest_dict = MultiKeyDict()


    def get_skeleton(
        self,
        construction: bool = False,
        analysis: bool = False,
        with_digest_placeholder: bool = False,
        with_index: bool = False,
        with_label: bool = True,
    ):
        content = self.get_skeleton_title(with_index)

        if construction and not analysis and self.description:
            content += f"\n{self.construction}"
        elif analysis and not construction and self.description:
            content += f"\n{self.analysis}"
        elif construction and analysis and self.description and with_label:
            content += f"\nDigest Construction: \n{self.construction}\nDigest Analysis: \n{self.analysis}\n"
        elif construction and analysis and self.description and not with_label:
            content += f"\n{self.construction}\n{self.analysis}"

        if with_digest_placeholder and self.depth != 0:
            content += f"\nExtracted relevant content from the given paper. If no related information is available for a particular section, retain the section title and just leave <EMPTY> in section description."
        return content
    
    def get_skeleton_title(self, with_index: bool = False):
        prefix = "#" * (self.depth + 1)
        if with_index and self.number_index:
            content = f"\n{prefix} {self.number_index} {self.title}"
        else:
            content = f"\n{prefix} {self.title}"
        return content

    def set_digest(self, key, digest_node):
        self.digest_dict[key] = digest_node

    def parse_description(self):
        construction_reg = re.compile(
            r"Digest Construction:\s*(.*)\s*Digest Analysis:", re.DOTALL
        )
        analysis_reg = re.compile(r"Digest Analysis:\s*(.*)", re.DOTALL)
        construction_match = construction_reg.search(self.description)
        if construction_match:
            self.construction = construction_match.group(1).strip()
        analysis_match = analysis_reg.search(self.description)
        if analysis_match:
            self.analysis = analysis_match.group(1).strip()


class Skeleton:
    def __init__(self, references_keys):
        self.is_compress_over = False
        self.references = set(references_keys)
        self.root = None
        self.raw_skeleton = ""

        self.suggestion = None
        self.eval_score = None
        self.eval_detail = None

    def parse_raw_skeleton(self, provide_title, raw_outline: str):
        try:
            raw_outline = parse_md_content(raw_outline)
            raw_outline = remove_illegal_bibkeys(raw_outline, self.references)
            lines = raw_outline.split("\n")
            title = lines[0].replace("#", "").strip()
            self.root = root = SkeletonNode(title=provide_title)
            section_stack = [(root, 1)]
            lines = lines[1:]

            for line in lines:
                depth, title = get_section_title(line)
                if depth > 0:
                    new_section = SkeletonNode(title=title)

                    while section_stack and section_stack[-1][1] >= depth:
                        section_stack[-1][0].description = section_stack[-1][
                            0
                        ].description.strip()
                        section_stack.pop()

                    if section_stack:
                        section_stack[-1][0].add_son(new_section)

                    section_stack.append((new_section, depth))
                else:
                    if len(line) > 0:
                        section_stack[-1][0].description += line + "\n"

            self.root.update_section()
            for node in self.root.all_section:
                node.parse_description()
            self.raw_skeleton = raw_outline
            # self.check_bibkeys()
        except Exception as e:
            logger.warning(f"Error in parsing skeleton {provide_title}: {e}\n{traceback.format_exc()}")
            self.root = None
            raise e
        return self

    def check_bibkeys(self):
        def str2list(raw_str):
            str_list = raw_str.split(",")
            str_list = [s.strip().replace("[", "").replace("]", "") for s in str_list]
            return str_list

        all_nodes = self.root.all_section
        references_reg = re.compile(r"\[(.*?)\]")
        ref_set = set()
        for node in all_nodes:
            description = node.description.strip()

            ref_lists = references_reg.findall(description)
            if ref_lists:
                for ref in ref_lists:
                    ref = str2list(ref)
                    ref_set.update(ref)

        if rest_bibkeys := ref_set - self.references:
            raise BibkeyNotFoundError(rest_bibkeys)

    def all_skeleton(
        self,
        construction=False,
        analysis=False,
        with_digest_placeholder=False,
        with_index=False,
        with_label=True,
    ):
        outline = []
        all_section = self.root.all_section

        for section in all_section:
            outline.append(
                section.get_skeleton(
                    construction,
                    analysis,
                    with_digest_placeholder,
                    with_index,
                    with_label,
                )
            )

        return "\n".join(outline).strip()

    def update(self, raw_outline):
        self.parse_raw_skeleton(self.survey_title, raw_outline)
        return self

    @property
    def survey_title(self):
        return self.root.title

