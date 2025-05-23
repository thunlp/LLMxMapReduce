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
            
            # 准备输出路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"output/{topic}_{timestamp}_crawl_result.jsonl"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 更新状态：爬取内容
            task_manager.update_task_status(task_id, TaskStatus.CRAWLING)
            logger.info(f"[任务 {task_id}] 开始爬取网页内容")
            
            # 执行爬取
            crawler = AsyncCrawler(model=self.search_model, infer_type="OpenAI")
            await crawler.run(
                topic=topic,
                url_list=url_list,
                crawl_output_file_path=output_path,
                top_n=top_n
            )
            
            logger.info(f"[任务 {task_id}] 爬取完成: {output_path}")
            return output_path
            
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
        
        # 准备输出文件路径
        if 'output_file' not in params or not params['output_file']:
            params['output_file'] = f"output/{original_topic}_{timestamp}_result.jsonl"
            os.makedirs('output', exist_ok=True)
        
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
            
            # 处理输入文件
            input_file_path = None
            
            if params.get('topic'):
                # 异步处理主题搜索
                input_file_path = asyncio.run(
                    self.topic_processor.process(task_id, params)
                )
                
                if not input_file_path:
                    raise ValueError("主题处理失败")
                    
            elif params.get('input_file'):
                input_file_path = params['input_file']
                if not os.path.exists(input_file_path):
                    raise ValueError(f"输入文件不存在: {input_file_path}")
            else:
                raise ValueError("必须指定topic或input_file参数")
            
            # 修改输入文件
            unique_title = task.get('expected_survey_title')
            modified_input = self._modify_input_file(
                input_file_path, unique_title, task_id
            )
            
            # 更新状态：处理中
            self.task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
            
            # 启动监控
            self._start_monitoring(task_id)
            
            # 提交到pipeline
            self.global_pipeline.put(modified_input)
            logger.info(f"[任务 {task_id}] 已提交到pipeline")
            
        except Exception as e:
            logger.error(f"[任务 {task_id}] 执行失败: {str(e)}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED, str(e))
    
    def _modify_input_file(self, input_file: str, unique_title: str, 
                          task_id: str) -> str:
        """
        修改输入文件，添加唯一标题和task_id
        
        Args:
            input_file: 原始输入文件路径
            unique_title: 唯一标题
            task_id: 任务ID
            
        Returns:
            修改后的文件路径
        """
        temp_file = f"{input_file}.{task_id}.tmp"
        
        with open(input_file, 'r', encoding='utf-8') as f_in:
            with open(temp_file, 'w', encoding='utf-8') as f_out:
                for line in f_in:
                    try:
                        data = json.loads(line.strip())
                        if 'title' in data:
                            data['title'] = unique_title
                            data['task_id'] = task_id
                        f_out.write(json.dumps(data, ensure_ascii=False) + '\n')
                    except json.JSONDecodeError:
                        f_out.write(line)
        
        logger.info(f"[任务 {task_id}] 创建修改后的输入文件: {temp_file}")
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
            temp_files = glob.glob(f"*.{task_id}.tmp")
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"[任务 {task_id}] 清理临时文件: {temp_file}")
        except Exception as e:
            logger.warning(f"[任务 {task_id}] 清理临时文件失败: {str(e)}") 