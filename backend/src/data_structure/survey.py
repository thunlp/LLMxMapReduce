from typing import List, Set
import time
import json

from .content import Content
from .digest import Digest
from .skeleton import Skeleton
from .multi_key_dict import MultiKeyDict
from src.utils.process_str import proc_title_to_str


    
class Survey:
    def __init__(self, json_data, task_id=None):
        self.title = json_data["title"]
        self.task_id = task_id # 添加task_id 字段，不会影响原本的代码
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
            
        result_dict = {
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
        
        if self.task_id:
            result_dict["task_id"] = self.task_id
            
        return result_dict

    def update_digests(self, digest_list: List):
        self.digests = MultiKeyDict()
        for digest in digest_list:
            self.digests[digest.bibkeys] = digest
        return self