import json
import random

from async_d import Node
from async_d import Sequential
from gevent.fileobject import FileObject
from threading import Lock

from src.data_structure.survey import Survey
from src.database import mongo_manager
from src.task_manager import get_task_manager
import logging
logger = logging.getLogger(__name__)


class EncodePipeline(Sequential):
    def __init__(self, configs, data_num, worker_num=1):
        self.configs = configs
        self.worker_num = worker_num
        self.data_num = data_num
        self.processed_count = 0
        self._count_lock = Lock()

        self.load_node = Node(
            self.load_survey, worker_num=self.worker_num
        )
        self.unpack_node = Node(
            self.unpack,
            is_data_iterable=True,
            worker_num=self.worker_num,
        )
        
        super().__init__(
            [
                self.load_node,
                self.unpack_node,
            ]
        )

    def load_survey(self, input_data):
        """
        加载Survey数据，支持两种输入模式：
        1. task_id (字符串) - 从数据库读取爬虫结果
        2. 文件路径 (字符串) - 从文件读取数据（向后兼容）
        """
        # 检查输入是否为task_id（新模式）
        # task_id通常是UUID格式，不包含路径分隔符且不以文件扩展名结尾
        if (isinstance(input_data, str) and 
            '/' not in input_data and 
            '\\' not in input_data and 
            not input_data.endswith(('.tmp', '.json', '.txt', '.jsonl'))):
            # 假设这是一个task_id，从数据库读取数据
            yield from self._load_from_database(input_data)
        else:
            # 假设这是一个文件路径，使用原有的文件读取逻辑
            yield from self._load_from_file(input_data)
    
    def _load_from_database(self, task_id: str):
        """从数据库读取爬虫结果并构建Survey"""
        try:
            logger.info(f"[EncodePipeline] 开始从数据库加载数据: task_id={task_id}")
            
            # 获取任务信息
            task_manager = get_task_manager()
            task = task_manager.get_task(task_id)
            if not task:
                logger.error(f"[EncodePipeline] 任务不存在: task_id={task_id}")
                return
            
            # 获取爬虫结果
            crawl_results = mongo_manager.get_crawl_results(task_id)
            if not crawl_results:
                logger.error(f"[EncodePipeline] 未找到爬虫结果: task_id={task_id}")
                return
            
            # 获取预期的survey标题
            expected_title = task.get('expected_survey_title', crawl_results.get('topic', 'Unknown Survey'))
            
            # 构建Survey数据结构
            survey_data = {
                'title': expected_title,
                'task_id': task_id,
                'papers': crawl_results.get('papers', []),
                'outline': [],  # 初始为空，后续由pipeline生成
                'txt': ''       # 初始为空，后续由pipeline生成
            }
            
            # 创建Survey对象
            survey = Survey(survey_data, task_id=task_id)
            
            if len(survey.papers) == 0:
                logger.error(f"[EncodePipeline] Survey没有论文数据: task_id={task_id}, title={survey.title}")
                return
            
            logger.info(f"[EncodePipeline] Survey从数据库加载成功: task_id={task_id}, title={survey.title}, papers_count={len(survey.papers)}")
            
            with self._count_lock:
                if self.data_num is not None:
                    if self.processed_count >= self.data_num:
                        return
                    self.processed_count += 1
            
            yield survey
            
        except Exception as e:
            logger.error(f"[EncodePipeline] 从数据库加载数据失败: task_id={task_id}, error={str(e)}")
    
    def _load_from_file(self, input_file):
        """从文件读取数据（向后兼容模式）"""
        logger.info(f"[EncodePipeline] 使用文件模式加载数据: {input_file}")
        
        with FileObject(input_file, "r") as f:
            for line in f:
                with self._count_lock:
                    if self.data_num is not None:
                        if self.processed_count >= self.data_num:
                            break
                        self.processed_count += 1
                
                data = json.loads(line)
                task_id = data.get('task_id')
                survey = Survey(data, task_id=task_id)
                
                if len(survey.papers) == 0:
                    logger.error(
                        f"Survey {survey.title} has no papers, "
                        f"skipping this survey."
                    )
                    continue
                    
                if task_id:
                    logger.info(f"Survey从文件加载成功: title={survey.title}, task_id={task_id}")
                else:
                    logger.warning(f"Survey从文件加载缺少task_id: title={survey.title}")
                    
                yield survey
            else:
                logger.info("All data in input file has been loaded.")
        
        with self._count_lock:
            if self.data_num is not None and self.processed_count < self.data_num:
                logger.warning(
                    f"Only {self.processed_count} data in input file, "
                    f"less than specified data_num {self.data_num}."
                )

    def unpack(self, survey):
        return survey
