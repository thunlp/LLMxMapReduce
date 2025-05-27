from gevent.queue import Queue, ShutDown, Empty
import random
from .treenode import TreeNode
import re
from src.exceptions import (
    BibkeyNotFoundError,
    StructureNotCorrespondingError,
    MdNotFoundError,
)
from ..utils.process_str import parse_md_content, remove_illegal_bibkeys
import logging
logger = logging.getLogger(__name__)

class ContentNode(TreeNode):
    def __init__(self, outline_node, digests, block_cycle_count):
        super().__init__()
        self.content = ""
        self.block_cycle_count = block_cycle_count
        self.digests = digests
        self.digest_nodes = outline_node.digest_dict
        self.outline_node = outline_node
        self.failure_count=0
        
        self.all_bibkeys = self._get_all_bibkeys()
        self.is_content_qualified = False

    def update_content(self, new_content, check_title=True):
        try:
            raw_content = parse_md_content(new_content)
            title_reg = r"^(#+\s*[\d\.]*\s+.*)"
            titles = re.findall(title_reg, raw_content, re.MULTILINE)
            for title in titles:
                raw_content = raw_content.replace(title, "")
            raw_content = remove_illegal_bibkeys(raw_content, self.all_bibkeys)
            self.content = raw_content.strip()
        except Exception as e:
            logger.warning(
                f"Error in parsing content (Survey: {self.survey_title}, index: {str(self.index)}): {e}"
            )
            raise e

    def _check_all_bibkey_exist(self):
        cite_reg = re.compile(r"\[([^\]]+)\]")
        bibkeys = self.all_bibkeys
        current_bibkeys = set()
        for match in cite_reg.finditer(self.content):
            bibkey_str = match.group(1)
            bibkey_list = bibkey_str.split(",")
            for bibkey in bibkey_list:
                current_bibkeys.add(bibkey.strip())
        return current_bibkeys - bibkeys

    def cite_papers(self):
        cite_reg = re.compile(r"\[([^\]]+)\]")
        cite_papers = set()
        for match in cite_reg.finditer(self.content):
            bibkey_str = match.group(1)
            bibkey_list = bibkey_str.split(",")
            for bibkey in bibkey_list:
                cite_papers.add(self.digests[bibkey.strip()])

        cite_papers = list(cite_papers)
        random.shuffle(cite_papers)

        def format_paper_content(digest):
            return f"**{digest.title}** (bibkey: {digest.bibkey}): \n{digest.origin_content}"

        cite_papers = [format_paper_content(digest) for digest in cite_papers]
        return cite_papers

    def titled_content(self, with_index=True):
        title = self.title(with_index)
        return f"{title.strip()}\n{self.content.strip()}"

    @property
    def survey_title(self):
        return self.outline_node.root.title
    
    @property
    def survey_label(self):
        survey_label = f"{self.survey_title}(Block cycle count: {self.block_cycle_count})"
        return survey_label

    def title(self, with_index=True):
        prefix = "#" * (self.depth + 1)
        if with_index:
            return f"{prefix} {self.number_index} {self.outline_node.title}"
        else:
            return f"{prefix} {self.outline_node.title}"

    def subcontents(self, with_index=True):
        subcontents = []

        def traverse(node):
            nonlocal subcontents
            subcontents.append(node.titled_content(with_index))
            for son in node.son:
                traverse(son)

        traverse(self)
        return "\n\n".join(subcontents[1:]).strip()

    def _get_all_bibkeys(self):
        return self.digests.keys()


class Content:
    def __init__(self, outline, digests, block_cycle_count):
        self.outline = outline
        self.digests = digests
        self.block_cycle_count = block_cycle_count
        self.root = None
        self.waiting_content = None
        self.is_finish = False

    def __iter__(self):
        self.is_finish = False
        return self

    def __next__(self):
        if not self.is_finish:
            try:
                content = self.waiting_content.get_nowait()
                return content
            except ShutDown as e:
                raise StopIteration()
            except Empty as e:
                return None
        else:
            raise StopIteration()

    def init_content(self):
        self.waiting_content = Queue()
        self.root = ContentNode(self.outline.root, self.digests, self.block_cycle_count)
        for section in self.outline.root.son:
            self._init_content_node(section, self.root)
        self.root.update_section()
        pass

    def _init_content_node(self, outline_node, parent_content_node):
        content_node = ContentNode(outline_node, self.digests, self.block_cycle_count)
        parent_content_node.add_son(content_node)
        for subsection in outline_node.son:
            self._init_content_node(subsection, content_node)
        if len(outline_node.son) == 0:  # leaf node
            self.waiting_content.put(content_node)

    def add_content(self, content_node: ContentNode):
        logger.info(f"Add content {content_node.title(with_index=True)}")
        father = content_node.father
        if all(son.is_content_qualified for son in father.son):
            if father != self.root:
                logger.info(f"Father {father.title()} is qualified, add to waiting queue")
                self.waiting_content.put(father)
            else:
                self.is_finish = True
                self.waiting_content.shutdown()
        else:
            unqualified_son = [
                son.title() for son in father.son if not son.is_content_qualified
            ]
            logger.info(
                f"Father {father.title()} is not qualified, unqualified son: {unqualified_son}"
            )

    @property
    def all_content(self):
        if self.root:
            all_section = self.root.all_section
            all_content = "\n".join([section.titled_content(with_index=True) for section in all_section])
            all_content.replace("# 0. ", "# ")
            return all_content

    @property
    def section_dict(self):
        if self.root:
            all_section = self.root.all_section
            section_dict = {}
            for section in all_section:
                section_dict[section.outline_node.title] = section
            return section_dict