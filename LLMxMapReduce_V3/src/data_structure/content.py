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
import json
from typing import List, Dict, Any, Optional
from .digest import Digest
from .skeleton import Skeleton
from src.data_structure.multi_key_dict import MultiKeyDict

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
        # BUG: 多级root追溯到根节点
        return self.outline_node.root.root.root.root.root.root.title
    
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
    
    def to_json(self):
        if isinstance(self.digests, MultiKeyDict):
            self.digests = self.digests.to_dict()
        elif not (isinstance(self.digests, dict) or self.digests is None):
            raise TypeError("digests must be a MultiKeyDict or dict")
        data = {
            'content': self.content,
            'block_cycle_count': self.block_cycle_count,
            'failure_count': self.failure_count,
            'all_bibkeys': list(self.all_bibkeys),
            'is_content_qualified': self.is_content_qualified,
            'outline_node': json.loads(self.outline_node.to_json()),  
            'digests': self.digests,
            'digest_nodes': {key: json.loads(node.to_json()) for key, node in self.digest_nodes.items()},
        }
        
        data.update(self._get_base_node_data())

        data['son'] = [json.loads(son.to_json()) for son in self.son]
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def _get_base_node_data(self):
        return {
            'name': self.name,
            'depth': self.depth,
            'index': self.index,
            'dirty': self.dirty,
            'number_index': self.number_index,
            'is_leaf': self.is_leaf,
            'former_section_ids': [node.index for node in self.former_section],
            'subsection_ids': [node.index for node in self.subsection]
        }

    @staticmethod
    def from_json(json_str, outline_node_dict, digest_dict):
        """
        Deserialize from JSON string to ContentNode object

        Args:
        json_str: Serialized JSON string
        outline_node_dict: Outline node dictionary (bibkey -> OutlineNode)
        digest_dict: Digest dictionary (bibkey -> Digest)
        
        Returns:
        ContentNode object
        """
        data = json.loads(json_str)
        
        outline_key = data['outline_node']['bibkey']
        outline_node = outline_node_dict.get(outline_key)
        
        node = ContentNode(
            outline_node=outline_node,
            digests=digest_dict,
            block_cycle_count=data['block_cycle_count']
        )
        
        node.content = data['content']
        node.failure_count = data['failure_count']
        node.all_bibkeys = set(data['all_bibkeys'])
        node.is_content_qualified = data['is_content_qualified']
        
        node.name = data['name']
        node.depth = data['depth']
        node.index = data['index']
        node.dirty = data['dirty']
        
        for son_data in data.get('son', []):
            son_node = ContentNode.from_json(
                json.dumps(son_data), 
                outline_node_dict, 
                digest_dict
            )
            node.add_son(son_node)  # 使用add_son方法自动设置father和root
        
        return node

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
                print(f"Content queue is shut down: {e}")
                raise StopIteration()
            except Empty as e:
                # print(f"No more content available: {e}")
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
        
    def to_json(self) -> str:
        if isinstance(self.digests, MultiKeyDict):
            self.digests = self.digests.to_dict()
        elif not (isinstance(self.digests, dict) or self.digests is None):
            raise TypeError("digests must be a MultiKeyDict or dict")
        
        content_dict = {
            'outline': json.loads(self.outline.to_json()) if self.outline else None,
            'digests': self.digests,
            'block_cycle_count': self.block_cycle_count,
            'root': self._serialize_root() if self.root else None,
            'waiting_content': self._serialize_queue(),
            'is_finish': self.is_finish
        }

        return json.dumps(content_dict, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str, outline: Optional[Skeleton] = None, digests: Optional[Digest] = None) -> 'Content':
        content_dict = json.loads(json_str)

        instance = cls(
            outline=outline or Skeleton.from_json(json.dumps(content_dict['outline'])) if content_dict['outline'] else None,
            digests=digests or MultiKeyDict.from_dict(content_dict['digests']) if content_dict['digests'] else None,
            block_cycle_count=content_dict['block_cycle_count']
        )
        
        if content_dict['root']:
            instance.root = cls._deserialize_root(content_dict['root'], instance.digests, instance.outline)
            instance.root.update_section()
        
        instance.waiting_content = cls._deserialize_queue(content_dict['waiting_content'], instance.digests, instance.outline)
        
        instance.is_finish = content_dict['is_finish']
        
        return instance
    
    def _serialize_root(self) -> Dict[str, Any]:
        if not self.root:
            return None
            
        def serialize_node(node: ContentNode) -> Dict[str, Any]:
            if isinstance(node.digests, MultiKeyDict):
                node.digests = node.digests.to_dict()
            elif not (isinstance(node.digests, dict) or node.digests is None):
                raise TypeError("digests must be a MultiKeyDict or dict")
            return {
                'content': node.content,
                'block_cycle_count': node.block_cycle_count,
                'digests': node.digests,
                'digest_nodes': node.digest_nodes,
                'outline_node': node.outline_node.title if node.outline_node else None,
                'failure_count': node.failure_count,
                'all_bibkeys': list(node.all_bibkeys) if node.all_bibkeys else [],
                'is_content_qualified': node.is_content_qualified,
                'sons': [serialize_node(son) for son in node.son]
            }
            
        return serialize_node(self.root)
    
    @staticmethod
    def _deserialize_root(data: Dict[str, Any], digests: MultiKeyDict, outline: Skeleton) -> ContentNode:
        if not data:
            return None
            
        def deserialize_node(node_data: Dict[str, Any]) -> ContentNode:
            outline_node = None
            if node_data['outline_node'] and outline and outline.root:
                for section in outline.root.all_section:
                    if section.title == node_data['outline_node']:
                        outline_node = section
                        break
            
            node = ContentNode(
                outline_node=outline_node,
                digests=digests,
                block_cycle_count=node_data['block_cycle_count']
            )
            
            node.content = node_data['content']
            node.failure_count = node_data['failure_count']
            node.all_bibkeys = set(node_data['all_bibkeys'])
            node.is_content_qualified = node_data['is_content_qualified']
            
            for son_data in node_data.get('sons', []):
                son_node = deserialize_node(son_data)
                node.add_son(son_node)
            
            return node
            
        return deserialize_node(data)
    
    def _serialize_queue(self) -> List[Dict[str, Any]]:
        queue_data = []
        if not self.waiting_content:
            return queue_data
            
        temp_queue = Queue()
        try:
            while True:
                item = self.waiting_content.get_nowait()
                queue_data.append(self._serialize_node(item))
                temp_queue.put(item)
        except Empty:
            pass
        
        while not temp_queue.empty():
            self.waiting_content.put(temp_queue.get())
            
        return queue_data
    
    @staticmethod
    def _deserialize_queue(queue_data: List[Dict[str, Any]], digests: Digest, outline: Skeleton) -> Queue:
        queue = Queue()
        for item_data in queue_data:
            node = Content._deserialize_node(item_data, digests, outline)
            if node:
                queue.put(node)
        return queue
    
    @staticmethod
    def _serialize_node(node: ContentNode) -> Dict[str, Any]:
        if isinstance(node.digests, MultiKeyDict):
            node.digests = node.digests.to_dict()
        elif not (isinstance(node.digests, dict) or node.digests is None):
            raise TypeError("digests must be a MultiKeyDict or dict")
        return {
            'content': node.content,
            'block_cycle_count': node.block_cycle_count,
            'digests': node.digests,
            'digest_nodes': node.digest_nodes,
            'outline_node': node.outline_node.title if node.outline_node else None,
            'failure_count': node.failure_count,
            'all_bibkeys': list(node.all_bibkeys) if node.all_bibkeys else [],
            'is_content_qualified': node.is_content_qualified,
            # 不序列化子节点，因为队列中的节点应该是叶子节点
        }
    
    @staticmethod
    def _deserialize_node(node_data: Dict[str, Any], digests: Digest, outline: Skeleton) -> Optional[ContentNode]:
        if not node_data:
            return None
            
        outline_node = None
        if node_data['outline_node'] and outline and outline.root:
            for section in outline.root.all_section:
                if section.title == node_data['outline_node']:
                    outline_node = section
                    break

        node = ContentNode(
            outline_node=outline_node,
            digests=digests,
            block_cycle_count=node_data['block_cycle_count']
        )
        
        node.content = node_data['content']
        node.failure_count = node_data['failure_count']
        node.all_bibkeys = set(node_data['all_bibkeys'])
        node.is_content_qualified = node_data['is_content_qualified']
        
        return node