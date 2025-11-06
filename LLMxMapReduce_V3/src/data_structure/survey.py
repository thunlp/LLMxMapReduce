from typing import List, Set, Dict, Any, TypeVar, Union
import time
import json

from .content import Content
from .digest import Digest
from .skeleton import Skeleton
from .multi_key_dict import MultiKeyDict
from src.utils.process_str import proc_title_to_str

T = TypeVar('T', bound='Survey')
    
class Survey:
    def __init__(self, json_data):
        self.title = json_data["title"]
        self.origin_outline = json_data.get("outline", [])
        self.origin_outline = "\n".join(self.origin_outline)
        self.origin_content = json_data.get("txt", "")

        self.papers = {}
        self.digests = MultiKeyDict()
        for paper in json_data["papers"]:
            if paper.get("txt", ""):
                paper["bibkey"] = proc_title_to_str(paper["title"])
                self.papers[paper["bibkey"]] = paper
        self.ref_str = "" # generate it after decode, in the format ## Reference\n [1] title url\n\n[2] title url\n\n

        self.skeleton = Skeleton(self.papers.keys())
        self.content = None

        self.block_cycle_count = 0
        
        self.skeleton_batch_size = 0
        self.digest_batch_size = 0
        
        self.block_avg_score = []
        self.conv_layer = 0
        self.receptive_field = 0
        self.top_k = 0
        self.result_num = 0
        
        self.self_refine_score = []
        self.best_of = 0
        self.refine_count = 0
        
        self.cite_ratio = 0

        self.iter_index = 0
        self.start_time = time.time()
        self.cost_time = 0
        
    def __iter__(self):
        self.iter_index = 0
        return self

    def __next__(self):
        if self.iter_index < len(self.digests):
            self.iter_index += 1
            return (
                self.title,
                self.skeleton.all_skeleton(
                    include_description=True
                ),
                list(self.digests.values())[self.iter_index - 1],
            )
        else:
            raise StopIteration()

    @property
    def abstracts(self):
        return {
            paper["bibkey"]: (paper["title"], paper["abstract"])
            for paper in self.papers.values()
        }
        
    @property
    def is_content_generate_finish(self):
        if self.content:
            return self.content.is_finish
        else:
            return False
        
    @property
    def survey_label(self):
        survey_label = f"{self.title}(Block cycle count: {self.block_cycle_count})"
        return survey_label

    def init_content(self):
        self.content = Content(self.skeleton, self.digests, self.block_cycle_count)
        self.content.init_content()

    def add_content(self, content):
        self.content.add_content(content)

    def update_outline(self, outline:str):
        self.skeleton.update(outline)
        return self

    def to_dict(self):
        current_time = time.time()
        cost_time = current_time - self.start_time + self.cost_time
        readable_time = time.strftime("%H:%M:%S", time.gmtime(cost_time))
        digests = []
        for digest in self.digests.values():
            digest = digest.to_dict()
            digests.append(digest)
            
        return {
            "title": self.title,
            "cost_time": readable_time,
            "block_cycle_count": self.block_cycle_count,
            "block_avg_score": self.block_avg_score,
            "self_refine_score": self.self_refine_score,
            "skeleton_batch_size" : self.skeleton_batch_size,
            "digest_batch_size" : self.digest_batch_size,
            "conv_layer": self.conv_layer,
            "receptive_field": self.receptive_field,
            "top_k": self.top_k,
            "result_num": self.result_num,
            "best_of": self.best_of,
            "refine_count": self.refine_count,
            "cite_ratio": self.cite_ratio,
            "outline": self.skeleton.all_skeleton(construction=True, analysis=True, with_index=True, with_label=False),
            "outline_suggestion": self.skeleton.suggestion,
            "outline_eval_score": self.skeleton.eval_score,
            "outline_eval_detail": self.skeleton.eval_detail,
            "content": self.content.all_content if self.content else "",
            "ref_str": self.ref_str,
            "digests": digests,
            "papers": list(self.papers.values()),
            "origin_content": self.origin_content,
            "origin_outline": self.origin_outline,
        }

    def update_digests(self, digest_list: List):
        self.digests = MultiKeyDict()
        for digest in digest_list:
            self.digests[digest.bibkeys] = digest
        return self
    
    # 为了方便将数据类进行网络传输，需要将该类的内容转为json，添加了json化和反json化方法
    def to_json(self) -> str:
        """将Survey对象转换为JSON字符串"""
        
        survey_dict = {
            'title': self.title,
            'origin_outline': self.origin_outline,
            'origin_content': self.origin_content,
            'papers': list(self.papers.values()),
            'ref_str': self.ref_str,
            'skeleton': json.loads(self.skeleton.to_json()) if self.skeleton else None,
            'content': json.loads(self.content.to_json()) if self.content else None,
            'block_cycle_count': self.block_cycle_count,
            'skeleton_batch_size': self.skeleton_batch_size,
            'digest_batch_size': self.digest_batch_size,
            'block_avg_score': self.block_avg_score,
            'conv_layer': self.conv_layer,
            'receptive_field': self.receptive_field,
            'top_k': self.top_k,
            'result_num': self.result_num,
            'self_refine_score': self.self_refine_score,
            'best_of': self.best_of,
            'refine_count': self.refine_count,
            'cite_ratio': self.cite_ratio,
            'iter_index': self.iter_index,
            'start_time': self.start_time,
            'cost_time': self.cost_time,
            'digests': [json.loads(digest.to_json()) for digest in self.digests.values()]
        }
        
        return json.dumps(survey_dict, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Survey':
        """从JSON字符串恢复Survey对象"""
        survey_dict = json.loads(json_str)
        
        # 处理papers
        papers = {}
        for paper in survey_dict['papers']:
            if paper.get("txt", ""):
                bibkey = proc_title_to_str(paper["title"])
                papers[bibkey] = paper
        
        # 重建Skeleton对象
        skeleton_data = survey_dict.get('skeleton')
        skeleton = Skeleton.from_json(json.dumps(skeleton_data)) if skeleton_data else None
        
        # 重建Digest对象列表
        digest_list = []
        for digest_data in survey_dict.get('digests', []):
            digest = Digest.from_json(json.dumps(digest_data), outline=skeleton)
            digest_list.append(digest)
        
        # 创建MultiKeyDict
        digests = MultiKeyDict()
        for digest in digest_list:
            digests[digest.bibkeys] = digest
        
        # 准备初始化数据
        init_data = {
            'title': survey_dict['title'],
            'outline': [survey_dict['origin_outline']],  # 构造原始格式
            'txt': survey_dict['origin_content'],
            'papers': list(papers.values())
        }
        
        # 创建Survey实例
        instance = cls(init_data)
        
        # 恢复其他属性
        instance.ref_str = survey_dict['ref_str']
        instance.skeleton = skeleton
        instance.block_cycle_count = survey_dict['block_cycle_count']
        instance.skeleton_batch_size = survey_dict['skeleton_batch_size']
        instance.digest_batch_size = survey_dict['digest_batch_size']
        instance.block_avg_score = survey_dict['block_avg_score']
        instance.conv_layer = survey_dict['conv_layer']
        instance.receptive_field = survey_dict['receptive_field']
        instance.top_k = survey_dict['top_k']
        instance.result_num = survey_dict['result_num']
        instance.self_refine_score = survey_dict['self_refine_score']
        instance.best_of = survey_dict['best_of']
        instance.refine_count = survey_dict['refine_count']
        instance.cite_ratio = survey_dict['cite_ratio']
        instance.iter_index = survey_dict['iter_index']
        instance.start_time = survey_dict['start_time']
        instance.cost_time = survey_dict['cost_time']
        instance.digests = digests
        
        # 重建Content对象
        content_data = survey_dict.get('content')
        if content_data and skeleton and digests:
            instance.content = Content.from_json(json.dumps(content_data), outline=skeleton, digests=digests)
        
        return instance