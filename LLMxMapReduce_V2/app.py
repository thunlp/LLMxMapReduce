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

# 设置Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.config_manager import get_config
from src.task_manager import get_task_manager
from src.pipeline_processor import PipelineTaskManager
from src.api_service import api_bp, set_pipeline_manager
from src.args import parse_args
from src.decode.decode_pipeline import DecodePipeline
from src.encode.encode_pipeline import EncodePipeline
from src.hidden.hidden_pipeline import HiddenPipeline
from async_d import Monitor, PipelineAnalyser, Pipeline

# 设置环境变量（开发环境默认值）
if not os.getenv('OPENAI_API_KEY'):
    os.environ['OPENAI_API_KEY'] = "7891b3e1-51cf-4979-9eae-ecdf4e411d5e"
if not os.getenv('OPENAI_API_BASE'):
    os.environ['OPENAI_API_BASE'] = "https://ark.cn-beijing.volces.com/api/v3"
if not os.getenv('SERPER_API_KEY'):
    os.environ['SERPER_API_KEY'] = "769aed5f5ca7b1ad747d71b57224eb53135d0069"


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
        self.encode_pipeline = EncodePipeline(
            self.model_config["encode"],
            data_num=1  # 全局pipeline模式，每次处理一个任务
        )
        
        self.hidden_pipeline = HiddenPipeline(
            self.model_config["hidden"],
            output_each_block=config.output_each_block,
            digest_group_mode=config.digest_group_mode,
            skeleton_group_size=config.skeleton_group_size,
            block_count=config.block_count,
            conv_layer=config.conv_layer,
            conv_kernel_width=config.conv_kernel_width,
            conv_result_num=config.conv_result_num,
            top_k=config.top_k,
            self_refine_count=config.self_refine_count,
            self_refine_best_of=config.self_refine_best_of,
            worker_num=config.parallel_num,
        )
        
        self.decode_pipeline = DecodePipeline(
            self.model_config["decode"],
            output_file=None,  # 全局pipeline模式，不使用固定输出文件
            worker_num=config.parallel_num,
            use_database=True  # 优先使用数据库存储
        )
        
        # 构建pipeline
        all_nodes = [self.encode_pipeline, self.hidden_pipeline, self.decode_pipeline]
        super().__init__(all_nodes, head=self.encode_pipeline, tail=self.decode_pipeline)
    
    def _connect_nodes(self):
        """连接各个节点"""
        self.encode_pipeline >> self.hidden_pipeline >> self.decode_pipeline


class Application:
    """主应用程序类"""
    
    def __init__(self, config_file=None):
        """
        初始化应用程序
        
        Args:
            config_file: 配置文件路径（可选）
        """
        # 加载配置
        self.config = get_config(config_file)
        
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
        
        # 初始化服务
        self._init_services()
    
    def _init_services(self):
        """初始化各项服务"""
        # 初始化Redis任务管理器
        try:
            task_manager = get_task_manager({
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
        
        # 初始化MongoDB（可选）
        try:
            from src.database import mongo_manager
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
            timeout=self.config.pipeline.timeout
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
        
        self.logger.info("应用程序已关闭")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='启动LLMxMapReduce Web服务')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--language', type=str, help='提示语言 (zh/en)')
    parser.add_argument('--host', type=str, help='服务器主机地址')
    parser.add_argument('--port', type=int, help='服务器端口')
    parser.add_argument('--redis-host', type=str, help='Redis主机地址')
    parser.add_argument('--redis-port', type=int, help='Redis端口')
    
    args = parser.parse_args()
    
    # 设置环境变量
    if args.language:
        os.environ['PROMPT_LANGUAGE'] = args.language
    if args.host:
        os.environ['API_HOST'] = args.host
    if args.port:
        os.environ['API_PORT'] = str(args.port)
    if args.redis_host:
        os.environ['REDIS_HOST'] = args.redis_host
    if args.redis_port:
        os.environ['REDIS_PORT'] = str(args.redis_port)
    
    # 创建并运行应用
    app = Application(config_file=args.config)
    app.run()


if __name__ == '__main__':
    main() 