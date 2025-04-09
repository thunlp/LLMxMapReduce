import json
from gevent.fileobject import FileObject
from async_d import Node
from async_d import Pipeline

from src.hidden.convolution_block.skeleton_module import SkeletonRefineModule
from .basic_modules.digest_module import DigestModule
from .basic_modules.skeleton_init_module import SkeletonInitModule
from .basic_modules.group_module import GroupModule
from src.data_structure.survey import Survey
import logging
logger = logging.getLogger(__name__)


class HiddenPipeline(Pipeline):
    def __init__(
        self,
        config,
        output_each_block,
        group_mode,
        skeleton_group_size,
        block_count,
        convolution_layer,
        convolution_kernel_size,
        convolution_result_num,
        top_k,
        self_refine_count,
        self_refine_best_of,
        worker_num=1,
    ):
        self.output_each_block = output_each_block
        self.block_count = block_count
        
        self.group_module = GroupModule(config["group"], group_mode, convolution_kernel_size)
        self.skeleton_init_module = SkeletonInitModule(config["skeleton"], skeleton_group_size)
        self.digest_module = DigestModule(config["digest"])
        self.regen_digest_module = DigestModule(config["digest"])
        self.skeleton_refine_module = SkeletonRefineModule(
            config["skeleton_refinement"],
            convolution_layer,
            convolution_kernel_size,
            convolution_result_num,
            top_k,
            self_refine_count,
            self_refine_best_of,
        )

        self.group_node = Node(self.group_module, worker_num=worker_num, queue_size=worker_num * 10)
        self.skeleton_init_node = Node(self.skeleton_init_module, worker_num=worker_num, queue_size=worker_num * 10)
        self.digest_node = Node(
            self.digest_module, put_deepcopy_data=True, worker_num=worker_num * 5, queue_size=worker_num * 20, discard_none_output=True
        )
        self.skeleton_refine_node = Node(self.skeleton_refine_module, worker_num=worker_num * 5, queue_size=worker_num * 20) 
        self.regen_digest_node = Node(
            self.digest_module, put_deepcopy_data=True, worker_num=worker_num * 5, queue_size=worker_num * 20, discard_none_output=True
        )
        self.output_node = Node(
            self.output_data, discard_none_output=True, worker_num=worker_num, queue_size=worker_num * 10
        )

        all_node = [
            self.group_node,
            self.skeleton_init_node,
            self.digest_node,
            self.skeleton_refine_node,
            # self.regen_digest_node,
            self.output_node,
        ]
            
        
        super().__init__(all_node, head=self.group_node, tail=self.output_node)

    def _connect_nodes(self):
        self.group_node >> self.skeleton_init_node >> self.digest_node >> self.output_node
        self.digest_node >> self.skeleton_refine_node >> self.digest_node
        self.digest_node.set_dst_criteria(self.skeleton_refine_node, self.iter_criteria)

    def output_data(self, survey):
        if not self.output_each_block and survey.block_cycle_count < self.block_count:
            logger.info(f"Survey {survey.title} is not reach block count, not output.")
            survey = None
        return survey

    def iter_criteria(self, survey):
        return survey.block_cycle_count < self.block_count