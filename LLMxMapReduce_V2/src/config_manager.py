"""
配置管理模块

集中管理应用程序的所有配置，支持环境变量和配置文件
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Redis配置"""
    host: str = 'localhost'
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    key_prefix: str = 'llm_task:'
    expire_time: int = 86400  # 24小时


@dataclass
class MongoConfig:
    """MongoDB配置"""
    uri: str = 'mongodb://localhost:27017/'
    database: str = 'llm_survey'
    collection: str = 'surveys'


@dataclass
class PipelineConfig:
    """Pipeline配置"""
    config_file: str = 'config/model_config_ds.json'  # 默认使用deepseek模型
    top_n: int = 50
    data_num: int = 1
    parallel_num: int = 1
    output_each_block: bool = False
    digest_group_mode: str = 'llm'
    skeleton_group_size: int = 3
    block_count: int = 1
    conv_layer: int = 6
    conv_kernel_width: int = 3
    conv_result_num: int = 10
    top_k: int = 6
    self_refine_count: int = 3
    self_refine_best_of: int = 3
    check_interval: int = 60  # 任务检查间隔
    timeout: int = 10800  # 任务超时时间, 3个小时


@dataclass
class APIConfig:
    """API服务配置"""
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False
    cors_enabled: bool = True


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    file_enabled: bool = True
    file_path: str = 'logs/web_demo.log'
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class AppConfig:
    """应用程序总配置"""
    redis: RedisConfig = field(default_factory=RedisConfig)
    mongo: MongoConfig = field(default_factory=MongoConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # 环境变量
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    serper_api_key: Optional[str] = None
    prompt_language: Optional[str] = None
    
    # 搜索模型配置
    search_model: str = 'gemini-2.0-flash-thinking-exp-01-21'
    
    def load_from_env(self):
        """从环境变量加载配置"""
        # Redis配置
        self.redis.host = os.getenv('REDIS_HOST', self.redis.host)
        self.redis.port = int(os.getenv('REDIS_PORT', str(self.redis.port)))
        self.redis.db = int(os.getenv('REDIS_DB', str(self.redis.db)))
        self.redis.password = os.getenv('REDIS_PASSWORD', self.redis.password)
        
        # MongoDB配置
        self.mongo.uri = os.getenv('MONGO_URI', self.mongo.uri)
        self.mongo.database = os.getenv('MONGO_DATABASE', self.mongo.database)
        self.mongo.collection = os.getenv('MONGO_COLLECTION', self.mongo.collection)
        
        # Pipeline配置
        self.pipeline.config_file = os.getenv('PIPELINE_CONFIG_FILE', self.pipeline.config_file)
        self.pipeline.parallel_num = int(os.getenv('PIPELINE_PARALLEL_NUM', str(self.pipeline.parallel_num)))
        
        # API配置
        self.api.host = os.getenv('API_HOST', self.api.host)
        self.api.port = int(os.getenv('API_PORT', str(self.api.port)))
        self.api.debug = os.getenv('API_DEBUG', 'false').lower() == 'true'
        
        # 日志配置
        self.logging.level = os.getenv('LOG_LEVEL', self.logging.level)
        self.logging.file_path = os.getenv('LOG_FILE_PATH', self.logging.file_path)
        
        # API密钥
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_api_base = os.getenv('OPENAI_API_BASE')
        self.serper_api_key = os.getenv('SERPER_API_KEY')
        self.prompt_language = os.getenv('PROMPT_LANGUAGE')
        
        # 搜索模型
        self.search_model = os.getenv('SEARCH_MODEL', self.search_model)
    
    def load_from_file(self, config_file: str):
        """从配置文件(json)加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新配置
            if 'redis' in config_data:
                self.redis = RedisConfig(**config_data['redis'])
            if 'mongo' in config_data:
                self.mongo = MongoConfig(**config_data['mongo'])
            if 'pipeline' in config_data:
                self.pipeline = PipelineConfig(**config_data['pipeline'])
            if 'api' in config_data:
                self.api = APIConfig(**config_data['api'])
            if 'logging' in config_data:
                self.logging = LoggingConfig(**config_data['logging'])
            
            # 其他配置
            for key in ['openai_api_key', 'openai_api_base', 'serper_api_key', 
                       'prompt_language', 'search_model']:
                if key in config_data:
                    setattr(self, key, config_data[key])
            
            logger.info(f"从配置文件加载配置: {config_file}")
            
        except Exception as e:
            logger.warning(f"加载配置文件失败: {config_file}, error: {str(e)}")
    
    def validate(self) -> bool:
        """验证配置的有效性"""
        # 检查必要的配置
        if not self.pipeline.config_file:
            logger.error("Pipeline配置文件未指定")
            return False
        
        # 检查配置文件是否存在
        if not os.path.exists(self.pipeline.config_file):
            # 尝试其他可能的路径（启发式）
            possible_paths = [
                self.pipeline.config_file,
                os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', self.pipeline.config_file),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), self.pipeline.config_file)
            ]
            
            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    self.pipeline.config_file = path
                    found = True
                    break
            
            if not found:
                logger.error(f"找不到Pipeline配置文件: {self.pipeline.config_file}")
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'redis': {
                'host': self.redis.host,
                'port': self.redis.port,
                'db': self.redis.db,
                'key_prefix': self.redis.key_prefix,
                'expire_time': self.redis.expire_time
            },
            'mongo': {
                'uri': self.mongo.uri,
                'database': self.mongo.database,
                'collection': self.mongo.collection
            },
            'pipeline': {
                'config_file': self.pipeline.config_file,
                'top_n': self.pipeline.top_n,
                'data_num': self.pipeline.data_num,
                'parallel_num': self.pipeline.parallel_num,
                'output_each_block': self.pipeline.output_each_block,
                'digest_group_mode': self.pipeline.digest_group_mode,
                'skeleton_group_size': self.pipeline.skeleton_group_size,
                'block_count': self.pipeline.block_count,
                'conv_layer': self.pipeline.conv_layer,
                'conv_kernel_width': self.pipeline.conv_kernel_width,
                'conv_result_num': self.pipeline.conv_result_num,
                'top_k': self.pipeline.top_k,
                'self_refine_count': self.pipeline.self_refine_count,
                'self_refine_best_of': self.pipeline.self_refine_best_of,
                'check_interval': self.pipeline.check_interval,
                'timeout': self.pipeline.timeout
            },
            'api': {
                'host': self.api.host,
                'port': self.api.port,
                'debug': self.api.debug,
                'cors_enabled': self.api.cors_enabled
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'file_enabled': self.logging.file_enabled,
                'file_path': self.logging.file_path,
                'max_bytes': self.logging.max_bytes,
                'backup_count': self.logging.backup_count
            },
            'search_model': self.search_model
        }


# 全局配置实例
_config_instance: Optional[AppConfig] = None


def get_config(config_file: Optional[str] = None) -> AppConfig:
    """
    获取配置实例（单例模式）
    
    Args:
        config_file: 配置文件路径（可选）
    
    Returns:
        AppConfig实例
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = AppConfig()
        
        # 先从文件加载
        if config_file and os.path.exists(config_file):
            _config_instance.load_from_file(config_file)
        
        # 再从环境变量加载（覆盖文件配置）
        _config_instance.load_from_env()
        
        # 验证配置
        if not _config_instance.validate():
            raise ValueError("配置验证失败")
        
        logger.info("配置加载完成")
    
    return _config_instance 