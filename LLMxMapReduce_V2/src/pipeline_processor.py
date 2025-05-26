"""
Pipeline处理器模块

负责Pipeline任务的处理、监控和生命周期管理
"""
import os
import json
import time
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from abc import ABC, abstractmethod

from src.task_manager import TaskStatus, get_task_manager
from src.database import mongo_manager
from src.path_validator import get_path_validator

logger = logging.getLogger(__name__)


class TaskProcessor(ABC):
    """任务处理器抽象基类"""
    
    @abstractmethod
    async def process(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        处理任务的核心方法
        
        Args:
            task_id: 任务ID
            params: 任务参数
            
        Returns:
            处理结果路径或None（失败时）
        """
        pass


class TopicSearchProcessor(TaskProcessor):
    """主题搜索处理器
    
    负责处理主题搜索和网页爬取任务
    """
    
    def __init__(self, search_model: str = 'gemini-2.0-flash-thinking-exp-01-21'):
        self.search_model = search_model
    
    async def process(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """执行主题搜索和爬取"""
        from src.LLM_search import LLM_search
        from src.async_crawl import AsyncCrawler
        
        task_manager = get_task_manager()
        
        try:
            # 提取参数
            topic = params.get('topic')
            description = params.get('description', '')
            top_n = int(params.get('top_n', 100))
            
            # 更新状态：生成查询
            task_manager.update_task_status(task_id, TaskStatus.SEARCHING)
            logger.info(f"[任务 {task_id}] 开始生成查询: {topic}")
            
            # 初始化检索器
            retriever = LLM_search(
                model=self.search_model,
                infer_type="OpenAI",
                engine='google',
                each_query_result=10
            )
            
            # 生成查询
            queries = retriever.get_queries(topic=topic, description=description)
            
            # 更新状态：搜索网页
            task_manager.update_task_status(task_id, TaskStatus.SEARCHING_WEB)
            logger.info(f"[任务 {task_id}] 开始搜索网页")
            
            # 搜索网页
            url_list = retriever.batch_web_search(
                queries=queries,
                topic=topic,
                top_n=int(top_n * 1.2)
            )
            
            # 更新状态：爬取内容
            task_manager.update_task_status(task_id, TaskStatus.CRAWLING)
            logger.info(f"[任务 {task_id}] 开始爬取网页内容")
            
            # 执行爬取
            # 现在将爬虫结果保存到 MongoDB 中，而不是本地文件
            crawler = AsyncCrawler(model=self.search_model, infer_type="OpenAI")
            await crawler.run(
                topic=topic,
                url_list=url_list,
                task_id=task_id,  # 传递 task_id
                top_n=top_n
            )
            
            logger.info(f"[任务 {task_id}] 爬取完成，结果已保存到 MongoDB")
            return task_id  # 返回 task_id 而不是文件路径
            
        except Exception as e:
            logger.error(f"[任务 {task_id}] 处理失败: {str(e)}")
            task_manager.update_task_status(task_id, TaskStatus.FAILED, str(e))
            return None


class PipelineTaskManager:
    """Pipeline任务管理器
    
    负责管理任务的完整生命周期，包括：
    - 任务提交和初始化
    - 任务状态监控
    - 任务结果处理
    - 资源清理
    """
    
    def __init__(self, 
                 global_pipeline,
                 check_interval: int = 30,
                 timeout: int = 3600):
        """
        初始化任务管理器
        
        Args:
            global_pipeline: 全局pipeline实例
            check_interval: 检查间隔（秒）
            timeout: 任务超时时间（秒）
        """
        self.global_pipeline = global_pipeline
        self.check_interval = check_interval
        self.timeout = timeout
        self.task_manager = get_task_manager()
        self.topic_processor = TopicSearchProcessor()
    
    def submit_task(self, params: Dict[str, Any]) -> str:
        """
        提交新任务
        
        Args:
            params: 任务参数
            
        Returns:
            任务ID
        """
        import uuid
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 生成唯一的综述标题
        original_topic = params.get('topic', 'unnamed_survey')
        unique_survey_title = f"{original_topic}_{task_id}_{timestamp}"
        
        # 不再需要准备输出文件路径，因为数据现在存储在 MongoDB 中
        
        # 扩展参数
        extended_params = params.copy()
        extended_params.update({
            'original_topic': original_topic,
            'expected_survey_title': unique_survey_title
        })
        
        # 创建任务
        self.task_manager.create_task(task_id, extended_params)
        
        # 保存额外字段
        self.task_manager.update_task_field(task_id, 'original_topic', original_topic)
        self.task_manager.update_task_field(task_id, 'expected_survey_title', unique_survey_title)
        
        logger.info(f"[任务 {task_id}] 已提交: {original_topic}")
        
        # 启动任务处理
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _run_task(self, task_id: str):
        """运行任务（在独立线程中）"""
        try:
            # 获取任务信息
            task = self.task_manager.get_task(task_id)
            if not task:
                logger.error(f"[任务 {task_id}] 任务不存在")
                return
            
            params = task['params']
            
            # 更新状态
            self.task_manager.update_task_status(task_id, TaskStatus.PREPARING)
            
            # 处理输入数据
            input_data = None
            
            if params.get('topic'):
                # 异步处理主题搜索
                result_task_id = asyncio.run(
                    self.topic_processor.process(task_id, params)
                )
                
                if not result_task_id:
                    raise ValueError("主题处理失败")
                
                # 从 MongoDB 获取爬虫结果
                crawl_results = mongo_manager.get_crawl_results(task_id)
                if not crawl_results:
                    raise ValueError(f"未找到爬虫结果: task_id={task_id}")
                
                input_data = crawl_results
                    
            elif params.get('input_file'):
                # 从文件读取数据（向后兼容）
                input_file_path = params['input_file']
                path_validator = get_path_validator()
                if not path_validator.validate_input_path(input_file_path):
                    raise ValueError(f"输入文件路径不安全或不存在: {input_file_path}")
                
                # 读取文件内容
                with open(input_file_path, 'r', encoding='utf-8') as f:
                    papers = []
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            if 'papers' in data:
                                papers.extend(data['papers'])
                        except json.JSONDecodeError:
                            continue
                    
                    input_data = {
                        'task_id': task_id,
                        'topic': params.get('topic', 'unknown'),
                        'papers': papers
                    }
            else:
                raise ValueError("必须指定topic或input_file参数")
            
            # 准备 pipeline 输入数据
            unique_title = task.get('expected_survey_title')
            pipeline_input = self._prepare_pipeline_input(
                input_data, unique_title, task_id
            )
            
            # 更新状态：处理中
            self.task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
            
            # 启动监控
            self._start_monitoring(task_id)
            
            # 提交到pipeline
            self.global_pipeline.put(pipeline_input)
            logger.info(f"[任务 {task_id}] 已提交到pipeline")
            
        except Exception as e:
            logger.error(f"[任务 {task_id}] 执行失败: {str(e)}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED, str(e))
    
    def _prepare_pipeline_input(self, input_data: Dict[str, Any], unique_title: str, 
                               task_id: str) -> str:
        """
        准备 pipeline 输入数据，创建临时文件供 pipeline 处理
        
        Args:
            input_data: 输入数据（从 MongoDB 或文件读取）
            unique_title: 唯一标题
            task_id: 任务ID
            
        Returns:
            临时文件路径
        """
        temp_file = f"pipeline_input_{task_id}.tmp"
        
        # 准备输出数据
        output_data = {
            'title': unique_title,
            'task_id': task_id,
            'papers': input_data.get('papers', [])
        }
        
        # 写入临时文件
        with open(temp_file, 'w', encoding='utf-8') as f_out:
            json.dump(output_data, f_out, ensure_ascii=False)
            f_out.write('\n')
        
        logger.info(f"[任务 {task_id}] 创建 pipeline 输入文件: {temp_file}")
        return temp_file
    
    def _start_monitoring(self, task_id: str):
        """启动任务监控"""
        monitor_thread = threading.Thread(
            target=self._monitor_task,
            args=(task_id,)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
    
    def _monitor_task(self, task_id: str):
        """监控任务完成状态"""
        logger.info(f"[任务 {task_id}] 开始监控")
        
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            # 检查数据库
            if self._check_completion_in_database(task_id):
                logger.info(f"[任务 {task_id}] 检测到任务已完成")
                self.task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
                break
            
            time.sleep(self.check_interval)
        else:
            # 超时
            logger.warning(f"[任务 {task_id}] 任务超时")
            self.task_manager.update_task_status(task_id, TaskStatus.TIMEOUT)
        
        # 清理临时文件
        self._cleanup_temp_files(task_id)
    
    def _check_completion_in_database(self, task_id: str) -> bool:
        """检查任务是否在数据库中完成"""
        try:
            if not mongo_manager:
                return False
            
            survey = mongo_manager.get_survey(task_id)
            return survey and survey.get('status') == 'completed'
            
        except Exception as e:
            logger.error(f"[任务 {task_id}] 数据库查询失败: {str(e)}")
            return False
    
    def _cleanup_temp_files(self, task_id: str):
        """清理临时文件"""
        import glob
        
        try:
            # 清理旧格式的临时文件
            temp_files = glob.glob(f"*.{task_id}.tmp")
            # 清理新格式的临时文件
            temp_files.extend(glob.glob(f"pipeline_input_{task_id}.tmp"))
            
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"[任务 {task_id}] 清理临时文件: {temp_file}")
        except Exception as e:
            logger.warning(f"[任务 {task_id}] 清理临时文件失败: {str(e)}") 