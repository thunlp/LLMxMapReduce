import re
import random
from typing import List
from copy import deepcopy, copy
from .treenode import TreeNode
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)
from ..utils.process_str import parse_md_content, remove_illegal_bibkeys, get_section_title
import logging

logger = logging.getLogger(__name__)


class DigestNode(TreeNode):
    def __init__(self, title, description=""):
        super().__init__()
        self.title = title
        self.description = description

    def content(self, with_index=False):
        prefix = "#" * (self.depth + 1)
        if with_index:
            content = f"\n{prefix} {self.number_index} {self.title}\n"
        else:
            content = f"\n{prefix} {self.title}\n"
        content += f"{self.description}"
        return content.strip()


class Digest:
    TOKEN_RATIO = 3.6875
    MAX_TOKEN = 800000
    MAX_LENGTH = int(
        MAX_TOKEN * TOKEN_RATIO
    )  # arxiv average length / token = 3.2, window size = 120,000, Prompt length 15k characters, assert max output length 16k token

    def __init__(self, paper_infos, survey_title):
        self.survey_title = survey_title
        self.paper_infos = []
        self.suggestions = {}
        self.failure_count=0
        self.root = None

        for paper_info in paper_infos:
            origin_content = self.pre_proc_paper(paper_info["txt"])
            abstract = paper_info.get("abstract", "")
            paper_token = paper_info.get("txt_token", self.MAX_TOKEN)
            if abstract:
                abstract = self._del_citation(abstract)
            else:
                abstract = origin_content[:500]
            if paper_token > self.MAX_TOKEN:
                logger.warning(
                    f"Total length of origin_content {paper_info['txt_token']} exceeds estimated max token {self.MAX_TOKEN}, scaling down content lengths."
                )
                origin_content = origin_content[: int(self.MAX_LENGTH)]
            paper = {
                "title": paper_info["title"],
                "bibkey": paper_info["bibkey"],
                "abstract": abstract,
                "content": origin_content,
                "origin_content": origin_content,
                "origin_token": paper_token,
            }
            self.paper_infos.append(paper)

    @classmethod
    def from_multiple_digests(cls, digests: List['Digest'], outline):
        assert len(digests) > 0, "No digests to merge"
        new_digests = copy(digests)
        single_digest = new_digests.pop(0)
        digest_content = single_digest.all_content(with_title=False, with_index=True)
        survey_title = single_digest.survey_title
        paper_infos = deepcopy(single_digest.paper_infos)
        suggestions = deepcopy(single_digest.suggestions)

        new_digest = cls([], survey_title)
        new_digest.paper_infos = paper_infos
        new_digest.parse_raw_digest(f"```markdown\n{digest_content}\n```", outline)
        all_section = new_digest.root.all_section

        for digest in new_digests:
            paper_infos.extend(deepcopy(digest.paper_infos))
            suggestions.update(deepcopy(digest.suggestions))
            for i, section in enumerate(digest.root.all_section):
                if section.description:
                    all_section[
                        i
                    ].description += f"---------------------\n{section.description}"

        new_digest.paper_infos = paper_infos
        new_digest.suggestions = suggestions
        return new_digest

    @property
    def bibkeys(self):
        return frozenset(paper["bibkey"] for paper in self.paper_infos)

    @property
    def abstract(self):
        return "\n---------------------\n".join(
            [
                f"Bibkey: '{paper['bibkey']}':\nAbstract:\n{paper['abstract'][:int(1500 * self.TOKEN_RATIO)]}".strip()
                for paper in self.paper_infos
            ]
        )

    def get_paper_infos(self):
        paper_infos = self.paper_infos
        random.shuffle(paper_infos)
        return paper_infos

    def get_raw_paper(self):
        paper_infos = self.paper_infos
        random.shuffle(paper_infos)
        return "\n---------------------\n".join(
            [
                f"Bibkey: {paper['bibkey']}:\nAbstract:\n{paper['origin_content']}".strip()
                for paper in paper_infos
            ]
        )

    def get_digest_from_str(self, raw_digest: str):
        md_content = parse_md_content(raw_digest)
        md_content = md_content.replace(
            "Extracted relevant content from the given paper. If no related information is available for a particular section, retain the section title and just leave <EMPTY> in section description.",
            "",
        )
        md_content = md_content.replace("<EMPTY>", "")
        md_content = remove_illegal_bibkeys(md_content, self.bibkeys)
        return md_content

    def parse_raw_digest(self, raw_digest: str, outline):
        try:
            md_content = self.get_digest_from_str(raw_digest)
            lines = md_content.split("\n")
            self.root = self._parse_md(lines)
            self.root.update_section()
            self.find_matching_section(self.root, outline)
            if len(self.root.all_section) != len(outline.root.all_section):
                raise StructureNotCorrespondingError(
                    f"Digest section number {len(self.root.all_section)} does not match outline section number {len(outline.root.all_section)}"
                )
        except Exception as e:
            logger.warning(
                f"Error in parsing digest (Survey: {self.survey_title} Bibkey: {', '.join(self.bibkeys)}): {e}"
            )
            self.root = None
            raise e
        return self

    def parse_suggestion(self, raw_result, bibkey):
        old_suggestions = self.suggestions
        try:
            suggestion = parse_md_content(raw_result, "suggestion")
            suggestion = remove_illegal_bibkeys(suggestion, self.bibkeys)
            self.suggestions[bibkey] = suggestion
        except Exception as e:
            logger.warning(
                f"Error in parsing suggestion (Survey: {self.survey_title} Bibkey: {', '.join(self.bibkeys)}): {e}"
            )
            self.suggestions = old_suggestions
            raise e

    def check_parse_raw_digest(self, raw_digest: str, outline):
        try:
            md_content = self.get_digest_from_str(raw_digest)
            lines = md_content.split("\n")
            root = self._parse_md(lines)
            root.update_section()
            self.find_matching_section(root, outline)
            # self.check_bibkeys()
        except Exception as e:
            logger.warning(
                f"Error in checking digest (Survey: {self.survey_title} Bibkey: {', '.join(self.bibkeys)}): {e}"
            )
            raise e
        return md_content

    def _del_citation(self, paper):
        references_reg = re.compile(r"\[(.*?)\]")
        paper = re.sub(references_reg, "", paper)
        return paper

    def pre_proc_paper(self, paper):
        ref_pattern = re.compile(
            r"(?i)^# (References|REFERENCE|REFERENCES|Bibliography)\s+.*?(?=^# |\Z)",
            re.DOTALL | re.MULTILINE,
        )
        paper = re.sub(ref_pattern, "", paper)

        paper = self._del_citation(paper)
        return paper

    def _parse_md(self, lines):
        section_stack = []
        for line in lines:
            depth, title = get_section_title(line)
            if depth > 0:
                new_section = DigestNode(title=title)

                while section_stack and section_stack[-1][1] >= depth:
                    section_stack.pop()

                if section_stack:
                    section_stack[-1][0].add_son(new_section)

                section_stack.append((new_section, depth))
            else:
                if line:
                    section_stack[-1][0].description += line + "\n"
        return section_stack[0][0]

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

        if rest_bibkeys := ref_set - self.bibkeys:
            raise BibkeyNotFoundError(rest_bibkeys)

    def find_matching_section(self, root, outline):
        def is_corresponding(outline_sec, digest_sec):
            outline_title = re.sub(r"\s+", " ", outline_sec.title.lower()).strip()
            digest_title = re.sub(r"\s+", " ", digest_sec.title.lower()).strip()
            ret = (
                outline_title == digest_title and outline_sec.index == digest_sec.index
            )
            return ret

        all_section = root.all_section
        for index, outline_section in enumerate(outline.root.all_section):
            cur_section = all_section[index]
            if is_corresponding(outline_section, cur_section):
                outline_section.set_digest(self.bibkeys, cur_section)
            else:
                raise StructureNotCorrespondingError(
                    f"Digest section title: '{cur_section.title}', index: '{cur_section.index}' does not match outline section title: '{outline_section.title}', index: '{outline_section.index}'"
                )

    def all_content(self, with_title=False, with_index=False):
        all_section = self.root.all_section
        title = f"**bibkeys: {', '.join(self.bibkeys)}**: \n"
        digest = "\n".join([section.content(with_index) for section in all_section])
        if with_title:
            content = title + digest
        else:
            content = digest
        return content

    def to_dict(self):
        return {
            "bibkey": ", ".join(self.bibkeys),
            "content": self.all_content(with_title=False, with_index=True),
        }
