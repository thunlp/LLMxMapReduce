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
from src.path_validator import get_path_validator
from src.database.mongo_manager import get_mongo_manager


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
    
    def __init__(self, 
                 top_n,
                 infer_type,
                 engine,
                 each_query_result,
                 search_model):
        self.search_model = search_model
        self.top_n = top_n
        self.infer_type = infer_type
        self.engine = engine
        self.each_query_result = each_query_result
    
    async def process(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """执行主题搜索和爬取"""
        from src.LLM_search import LLM_search
        from src.async_crawl import AsyncCrawler
        
        task_manager = get_task_manager()
        
        try:
            # 提取参数
            topic = params.get('topic')
            description = params.get('description', '')
            top_n = int(params.get('top_n', self.top_n))
            
            # 更新状态：生成查询
            task_manager.update_task_status(task_id, TaskStatus.SEARCHING)
            logger.info(f"[任务 {task_id}] 开始生成查询: {topic}")
            
            # 初始化检索器
            retriever = LLM_search(
                model=self.search_model,
                infer_type=self.infer_type,
                engine=self.engine,
                each_query_result=self.each_query_result
            )
            
            # 生成查询 - 添加详细的错误处理
            # todo debug for now, not get queries
            # try:
            #     queries = retriever.get_queries(topic=topic, description=description)
            #     if not queries:
            #         raise ValueError("生成的查询列表为空")
            #     logger.info(f"[任务 {task_id}] 查询生成成功，共生成 {len(queries)} 个查询")
            # except Exception as e:
            #     error_msg = f"查询生成失败: {str(e)}"
            #     logger.error(f"[任务 {task_id}] {error_msg}")
            #     task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
            #     return None
            
            # 更新状态：搜索网页
            task_manager.update_task_status(task_id, TaskStatus.SEARCHING_WEB)
            logger.info(f"[任务 {task_id}] 开始搜索网页")
            
            # 搜索网页 - 添加详细的错误处理
            # try:
            #     url_list = retriever.batch_web_search(
            #         queries=queries,
            #         topic=topic,
            #         top_n=int(top_n * 1.2)
            #     )
            #     if not url_list:
            #         raise ValueError("搜索到的URL列表为空")
            #     logger.info(f"[任务 {task_id}] 网页搜索成功，共找到 {len(url_list)} 个URL")
            # except Exception as e:
            #     error_msg = f"网页搜索失败: {str(e)}"
            #     logger.error(f"[任务 {task_id}] {error_msg}")
            #     task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
            #     return None
            
            # 更新状态：爬取内容
            task_manager.update_task_status(task_id, TaskStatus.CRAWLING)
            logger.info(f"[任务 {task_id}] 开始爬取网页内容")
            
            # 执行爬取 - 添加详细的错误处理
            try:
                crawler = AsyncCrawler(model=self.search_model, infer_type="OpenAI")
                await crawler.run(
                    topic=topic,
                    url_list=[], # todo debug for now, not get url_list
                    task_id=task_id,
                    top_n=top_n
                )
                
                # 从 MongoDB 获取爬虫结果
                from src.database.mongo_manager import get_mongo_manager
                mongo_manager = get_mongo_manager()
                crawl_results = mongo_manager.get_crawl_results(task_id)
                if not crawl_results or not crawl_results.get('papers'):
                    raise ValueError("爬取结果为空或保存失败")
                
                papers_count = len(crawl_results.get('papers', []))
                logger.info(f"[任务 {task_id}] 爬取完成，成功获取 {papers_count} 篇论文")
                
            except Exception as e:
                error_msg = f"网页爬取失败: {str(e)}"
                logger.error(f"[任务 {task_id}] {error_msg}")
                task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
                return None

            logger.info(f"[任务 {task_id}] 主题搜索和爬取阶段完成")
            return task_id  
            
        except Exception as e:
            error_msg = f"主题搜索处理器异常: {str(e)}"
            logger.error(f"[任务 {task_id}] {error_msg}")
            task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
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
                 check_interval: int = 60,
                 timeout: int = 86400,
                 **kwargs):
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

        if 'use_search' in kwargs and kwargs['use_search']:
            if 'search_model' not in kwargs:
                raise ValueError("请提供search_model参数")
            if 'top_n' not in kwargs:
                raise ValueError("请提供top_n参数")
            if 'infer_type' not in kwargs:
                raise ValueError("请提供infer_type参数")
            if 'engine' not in kwargs:
                raise ValueError("请提供engine参数")
            if 'each_query_result' not in kwargs:
                raise ValueError("请提供each_query_result参数")
            
            # 打印日志配置信息
            logger.info(f"使用搜索引擎: {kwargs['use_search']}")
            logger.info(f"搜索模型: {kwargs['search_model']}")
            logger.info(f"每个查询结果数量: {kwargs['each_query_result']}")
            logger.info(f"推理类型: {kwargs['infer_type']}")
            logger.info(f"搜索引擎: {kwargs['engine']}")

            self.topic_processor = TopicSearchProcessor(
                search_model=kwargs['search_model'],
                top_n=kwargs['top_n'],
                infer_type=kwargs['infer_type'],
                engine=kwargs['engine'],
                each_query_result=kwargs['each_query_result']
            )
    
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
        
        # 扩展参数
        extended_params = params.copy()
        extended_params.update({
            'original_topic': original_topic,
            'expected_survey_title': unique_survey_title
        })
        
        # 创建任务
        self.task_manager.create_task(task_id, extended_params)
        
        # 保存额外字段 - 这些字段用于后续的pipeline处理和结果标识
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
            
            # 更新状态：准备中
            self.task_manager.update_task_status(task_id, TaskStatus.PREPARING)
            logger.info(f"[任务 {task_id}] 开始准备任务")
            
            # 处理输入数据
            input_data = None
            
            if params.get('topic'):
                # 异步处理主题搜索
                result_task_id = asyncio.run(
                    self.topic_processor.process(task_id, params)
                )
                
                if not result_task_id:
                    # TopicSearchProcessor已经更新了失败状态，这里直接返回
                    return
                
                # 从 MongoDB 获取爬虫结果
                from src.database.mongo_manager import get_mongo_manager
                mongo_manager = get_mongo_manager()
                crawl_results = mongo_manager.get_crawl_results(task_id)
                if not crawl_results:
                    error_msg = f"未找到爬虫结果: task_id={task_id}"
                    logger.error(f"[任务 {task_id}] {error_msg}")
                    self.task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
                    return
                
                input_data = crawl_results
                logger.info(f"[任务 {task_id}] 成功获取爬虫数据，论文数量: {len(crawl_results.get('papers', []))}")
                    
            elif params.get('input_file'):
                # 向后兼容：从文件读取数据（正式场景下不应该被激发）
                logger.warning(f"[任务 {task_id}] 使用向后兼容的文件输入模式")
                input_file_path = params['input_file']
                path_validator = get_path_validator()
                if not path_validator.validate_input_path(input_file_path):
                    error_msg = f"输入文件路径不安全或不存在: {input_file_path}"
                    logger.error(f"[任务 {task_id}] {error_msg}")
                    self.task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
                    return
                
                # 读取文件内容
                try:
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
                        logger.info(f"[任务 {task_id}] 从文件读取数据完成，论文数量: {len(papers)}")
                except Exception as e:
                    error_msg = f"读取输入文件失败: {str(e)}"
                    logger.error(f"[任务 {task_id}] {error_msg}")
                    self.task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
                    return
            else:
                error_msg = "必须指定topic或input_file参数"
                logger.error(f"[任务 {task_id}] {error_msg}")
                self.task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
                return
            
            # 验证输入数据
            if not input_data or not input_data.get('papers'):
                error_msg = "输入数据为空或不包含论文"
                logger.error(f"[任务 {task_id}] {error_msg}")
                self.task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
                return
            
            # 更新状态：处理中
            self.task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
            logger.info(f"[任务 {task_id}] 开始Pipeline处理")
            
            # 启动监控
            self._start_monitoring(task_id)
            
            # 直接提交task_id到pipeline，让EncodePipeline从数据库读取数据
            self.global_pipeline.put(task_id)
            logger.info(f"[任务 {task_id}] 已提交到Pipeline")
            
        except Exception as e:
            error_msg = f"任务执行异常: {str(e)}"
            logger.error(f"[任务 {task_id}] {error_msg}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg)
    
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
        logger.info(f"[任务 {task_id}] 开始监控Pipeline处理状态")
        
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            # 检查数据库中的完成状态
            if self._check_completion_in_database(task_id):
                logger.info(f"[任务 {task_id}] 检测到Pipeline处理已完成")
                self.task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
                break
            
            # 检查任务是否已经失败
            task = self.task_manager.get_task(task_id)
            if task and task.get('status') == TaskStatus.FAILED.value:
                logger.info(f"[任务 {task_id}] 检测到任务已标记为失败，停止监控")
                break
            
            time.sleep(self.check_interval)
        else:
            # 超时处理
            logger.warning(f"[任务 {task_id}] Pipeline处理超时")
            self.task_manager.update_task_status(task_id, TaskStatus.TIMEOUT, "Pipeline处理超时")
        
        logger.info(f"[任务 {task_id}] 监控结束")
    
    def _check_completion_in_database(self, task_id: str) -> bool:
        """检查任务是否在数据库中完成"""
        try:
            # 在运行时获取mongo_manager，确保获取到正确配置的实例
            from src.database.mongo_manager import get_mongo_manager
            mongo_manager = get_mongo_manager()
            
            if not mongo_manager:
                return False
            
            survey = mongo_manager.get_survey(task_id)
            is_completed = survey and survey.get('status') == 'completed'
            
            if is_completed:
                logger.debug(f"[任务 {task_id}] 在数据库中找到完成的Survey")
            
            return is_completed
            
        except Exception as e:
            logger.error(f"[任务 {task_id}] 数据库查询失败: {str(e)}")
            return False 