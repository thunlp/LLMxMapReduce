"""
LLMxMapReduce Web服务主程序

基于事件驱动架构的综述生成服务
支持Redis任务管理、MongoDB数据存储和分布式部署
"""
import os
import sys
import json
import logging
import argparse
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 设置Python路径，防止包的导入问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.config_manager import get_config
from src.task_manager import get_task_manager
from src.pipeline_processor import PipelineTaskManager
from src.api_service import api_bp, set_pipeline_manager
from src.decode.decode_pipeline import DecodePipeline
from src.encode.encode_pipeline import EncodePipeline
from src.hidden.hidden_pipeline import HiddenPipeline
from async_d import Monitor, PipelineAnalyser, Pipeline
from src.database import init_mongo_manager


def setup_logging(config):
    """
    配置日志系统
    
    Args:
        config: 日志配置对象
    """
    # 创建日志目录
    if config.file_enabled:
        log_dir = os.path.dirname(config.file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))
    
    # 清除现有处理器
    root_logger.handlers = []
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.level))
    console_formatter = logging.Formatter(config.format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if config.file_enabled:
        file_handler = RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, config.level))
        file_formatter = logging.Formatter(config.format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # 抑制第三方库的日志
    for logger_name in ['httpx', 'openai', 'urllib3', 'requests']:
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


class EntirePipeline(Pipeline):
    """完整的Pipeline流水线"""
    
    def __init__(self, config):
        """
        初始化Pipeline
        
        Args:
            config: Pipeline配置对象
        """
        # 加载模型配置文件
        with open(config.config_file, "r") as f:
            self.model_config = json.load(f)
        
        self.config = config
        
        # 初始化各个阶段
        # ! 三个pipeline的默认并发都是默认为1，不知道提高并发系统有没有风险
        self.encode_pipeline = EncodePipeline(self.model_config["encode"])
        
        self.hidden_pipeline = HiddenPipeline(
            self.model_config["hidden"],
            output_each_block=config.output_each_block,
            group_mode=config.digest_group_mode,
            skeleton_group_size=config.skeleton_group_size,
            block_count=config.block_count,
            convolution_layer=config.conv_layer,
            convolution_kernel_size=config.conv_kernel_width,
            convolution_result_num=config.conv_result_num,
            top_k=config.top_k,
            self_refine_count=config.self_refine_count,
            self_refine_best_of=config.self_refine_best_of,
            worker_num=config.parallel_num, 
        )
        
        self.decode_pipeline = DecodePipeline(
            self.model_config["decode"],
            output_file=None,
            worker_num=config.parallel_num,
            use_database=True  # 使用数据库
        )
        
        # 构建pipeline
        all_nodes = [self.encode_pipeline, self.hidden_pipeline, self.decode_pipeline]
        super().__init__(all_nodes, head=self.encode_pipeline, tail=self.decode_pipeline)
    
    def _connect_nodes(self):
        """连接各个节点"""
        self.encode_pipeline >> self.hidden_pipeline >> self.decode_pipeline


class Application:
    """主应用程序类"""
    
    def __init__(self):
        """
        初始化应用程序
        """
        # 加载配置
        self.config = get_config()
        
        # 设置日志
        self.logger = setup_logging(self.config.logging)
        self.logger.info("应用程序初始化开始")
        
        # 初始化Flask应用
        self.app = Flask(__name__)
        if self.config.api.cors_enabled:
            CORS(self.app)
        
        # 注册API蓝图
        self.app.register_blueprint(api_bp)
        
        # 初始化组件
        self.global_pipeline = None
        self.pipeline_monitor = None
        self.pipeline_task_manager = None
        self.task_manager = None
        
        # 初始化服务
        self._init_services()
    
    def _init_services(self):
        """初始化必要的组件"""
        # 初始化Redis任务管理器
        try:
            self.task_manager = get_task_manager({
                'host': self.config.redis.host,
                'port': self.config.redis.port,
                'db': self.config.redis.db,
                'password': self.config.redis.password,
                'key_prefix': self.config.redis.key_prefix,
                'expire_time': self.config.redis.expire_time
            })
            self.logger.info("Redis任务管理器初始化成功")
        except Exception as e:
            self.logger.error(f"Redis初始化失败: {str(e)}")
            raise
        
        # 初始化MongoDB
        try:
            mongo_manager = init_mongo_manager(self.config.mongo)
            if mongo_manager.connect():
                self.logger.info("MongoDB连接成功")
                stats = mongo_manager.get_stats()
                self.logger.info(f"数据库状态: 共有 {stats['total_surveys']} 个综述记录")
            else:
                self.logger.warning("MongoDB连接失败，将仅使用文件存储")
        except Exception as e:
            self.logger.warning(f"MongoDB初始化失败: {str(e)}")
        
        # 初始化全局Pipeline
        self._init_global_pipeline()
        
        # 初始化Pipeline任务管理器
        self.pipeline_task_manager = PipelineTaskManager(
            global_pipeline=self.global_pipeline,
            check_interval=self.config.pipeline.check_interval,
            timeout=self.config.pipeline.timeout,
            use_search=self.config.pipeline.use_search,
            search_model=self.config.pipeline.search_model,
            top_n=self.config.pipeline.top_n,
            infer_type=self.config.pipeline.search_model_infer_type,
            engine=self.config.pipeline.search_engine,
            each_query_result=self.config.pipeline.search_each_query_result
        )
        
        # 设置API服务的Pipeline管理器
        set_pipeline_manager(self.pipeline_task_manager)
        
        self.logger.info("所有服务初始化完成")
    
    def _init_global_pipeline(self):
        """初始化全局Pipeline"""
        self.logger.info("正在初始化全局Pipeline...")
        
        # 创建Pipeline实例
        self.global_pipeline = EntirePipeline(self.config.pipeline)
        
        # 配置分析器和监控器
        pipeline_analyser = PipelineAnalyser()
        pipeline_analyser.register(self.global_pipeline)
        
        self.pipeline_monitor = Monitor(report_interval=60)
        self.pipeline_monitor.register(pipeline_analyser)
        self.pipeline_monitor.start()
        
        # 启动Pipeline
        self.global_pipeline.start()
        
        self.logger.info("全局Pipeline已启动")
    
    def get_system_status(self):
        """获取系统状态信息"""
        status = {
            'pipeline_running': False,
            'task_manager_connected': False,
            'active_tasks': 0,
            'total_tasks': 0
        }
        
        # Pipeline状态
        if self.global_pipeline:
            status['pipeline_running'] = self.global_pipeline.is_start
        
        # 任务管理器状态
        if self.task_manager:
            try:
                status['task_manager_connected'] = self.task_manager.health_check()
                status['active_tasks'] = self.task_manager.get_active_task_count()
                all_tasks = self.task_manager.list_tasks(limit=1000)
                status['total_tasks'] = len(all_tasks)
            except Exception as e:
                self.logger.error(f"获取任务管理器状态失败: {str(e)}")
        
        return status
    
    def run(self):
        """运行应用程序"""
        self.logger.info(f"Web服务器启动在 {self.config.api.host}:{self.config.api.port}")
        
        try:
            self.app.run(
                host=self.config.api.host,
                port=self.config.api.port,
                debug=self.config.api.debug
            )
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在关闭服务...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        if self.global_pipeline:
            self.logger.info("正在关闭全局Pipeline...")
            try:
                self.global_pipeline.end()
                self.logger.info("全局Pipeline已关闭")
            except Exception as e:
                self.logger.error(f"关闭Pipeline时出错: {str(e)}")
        
        # 清理任务管理器
        if self.task_manager:
            self.logger.info("正在清理任务管理器...")
            try:
                # 清理过期任务
                expired_count = self.task_manager.cleanup_expired_tasks()
                if expired_count > 0:
                    self.logger.info(f"清理了 {expired_count} 个过期任务")
                
                # 获取活跃任务数量
                active_count = self.task_manager.get_active_task_count()
                if active_count > 0:
                    self.logger.warning(f"仍有 {active_count} 个活跃任务未完成")
                
                self.logger.info("任务管理器清理完成")
            except Exception as e:
                self.logger.error(f"清理任务管理器时出错: {str(e)}")
        
        self.logger.info("应用程序已关闭")


def main():
    """主函数"""
    app = Application()
    app.run()


if __name__ == '__main__':
    main() 