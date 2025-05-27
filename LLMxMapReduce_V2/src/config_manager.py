"""
配置管理模块

集中管理应用程序的所有配置，支持环境变量和配置文件
"""
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class RedisConfig:
    """Redis配置"""
    # host, port, db 拥有默认值的原因在于这里实在是太常见了！
    host: str = 'localhost'
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    key_prefix: Optional[str] = None
    expire_time: Optional[int] = None


@dataclass
class MongoConfig:
    """MongoDB配置"""
    database: str = ''
    collection: str = ''
    uri: str = 'mongodb://localhost:27017/'


@dataclass
class PipelineConfig:
    """Pipeline配置"""
    config_file: str = ''
    top_n: int = 0
    data_num: int = 0
    parallel_num: int = 1
    output_each_block: bool = False
    digest_group_mode: str = ''
    skeleton_group_size: int = 0
    block_count: int = 0
    conv_layer: int = 0
    conv_kernel_width: int = 0
    conv_result_num: int = 0
    top_k: int = 0
    self_refine_count: int = 0
    self_refine_best_of: int = 0
    check_interval: int = 0
    timeout: int = 0
    use_search: bool = False
    search_model: str = ''
    search_model_infer_type: str = ''
    search_engine: str = ''
    search_each_query_result: int = 0


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
    
    def load_from_env(self):
        """从环境变量加载配置"""
        def get_required_env(key: str, value_type=str):
            """获取必需的环境变量，如果不存在则抛出异常"""
            value = os.getenv(key)
            if value is None:
                raise ValueError(f"必需的环境变量 {key} 未设置")
            
            if value_type == int:
                try:
                    return int(value)
                except ValueError:
                    raise ValueError(f"环境变量 {key} 的值 '{value}' 不是有效的整数")
            elif value_type == bool:
                return value.lower() in ('true', '1', 'yes', 'on')
            return value
        
        def get_optional_env(key: str, default_value=None, value_type=str):
            """获取可选的环境变量"""
            value = os.getenv(key)
            if value is None:
                return default_value
            
            if value_type == int:
                try:
                    return int(value)
                except ValueError:
                    logger.warning(f"环境变量 {key} 的值 '{value}' 不是有效的整数，使用默认值 {default_value}")
                    return default_value
            elif value_type == bool:
                return value.lower() in ('true', '1', 'yes', 'on')
            return value
        
        # Redis配置 - 必需，但是有默认值（业界常用）
        self.redis.host = get_optional_env('REDIS_HOST', 'localhost')
        self.redis.port = get_optional_env('REDIS_PORT', 6379, int)
        self.redis.db = get_optional_env('REDIS_DB', 0, int)

        # Redis密码和前缀可选
        self.redis.password = get_optional_env('REDIS_PASSWORD')
        self.redis.key_prefix = get_optional_env('REDIS_KEY_PREFIX')
        self.redis.expire_time = get_optional_env('REDIS_EXPIRE_TIME', value_type=int)
        
        # MongoDB配置 - 必需
        self.mongo.uri = get_optional_env('MONGO_URI', 'mongodb://localhost:27017/')
        self.mongo.database = get_required_env('MONGO_DATABASE')
        self.mongo.collection = get_required_env('MONGO_COLLECTION')
        
        # Pipeline配置 - 必需
        self.pipeline.config_file = get_required_env('PIPELINE_CONFIG_FILE')
        self.pipeline.parallel_num = get_required_env('PIPELINE_PARALLEL_NUM', int)
        self.pipeline.top_n = get_required_env('PIPELINE_TOP_N', int)
        self.pipeline.data_num = get_required_env('PIPELINE_DATA_NUM', int)
        self.pipeline.output_each_block = get_required_env('PIPELINE_OUTPUT_EACH_BLOCK', bool)
        self.pipeline.digest_group_mode = get_required_env('PIPELINE_DIGEST_GROUP_MODE')
        self.pipeline.skeleton_group_size = get_required_env('PIPELINE_SKELETON_GROUP_SIZE', int)
        self.pipeline.block_count = get_required_env('PIPELINE_BLOCK_COUNT', int)
        self.pipeline.conv_layer = get_required_env('PIPELINE_CONV_LAYER', int)
        self.pipeline.conv_kernel_width = get_required_env('PIPELINE_CONV_KERNEL_WIDTH', int)
        self.pipeline.conv_result_num = get_required_env('PIPELINE_CONV_RESULT_NUM', int)
        self.pipeline.top_k = get_required_env('PIPELINE_TOP_K', int)
        self.pipeline.self_refine_count = get_required_env('PIPELINE_SELF_REFINE_COUNT', int)
        self.pipeline.self_refine_best_of = get_required_env('PIPELINE_SELF_REFINE_BEST_OF', int)
        self.pipeline.check_interval = get_required_env('PIPELINE_CHECK_INTERVAL', int)
        self.pipeline.timeout = get_required_env('PIPELINE_TIMEOUT', int)
        self.pipeline.use_search = get_required_env('PIPELINE_USE_SEARCH', bool)
        
        # 搜索的功能处理模块，唯一在use_search为True时才需要用到
        self.pipeline.search_model = get_optional_env('PIPELINE_SEARCH_MODEL')
        self.pipeline.search_model_infer_type = get_optional_env('PIPELINE_SEARCH_MODEL_INFER_TYPE')
        self.pipeline.search_engine = get_optional_env('PIPELINE_SEARCH_ENGINE')
        self.pipeline.search_each_query_result = get_optional_env('PIPELINE_SEARCH_EACH_QUERY_RESULT', int)
        
        # API配置 - 必需
        self.api.host = get_optional_env('API_HOST', '0.0.0.0')
        self.api.port = get_optional_env('API_PORT', 5000, int)
        self.api.debug = get_optional_env('API_DEBUG', False, bool)
        self.api.cors_enabled = get_optional_env('API_CORS_ENABLED', True, bool)
        
        # 日志配置 - 必需
        self.logging.level = get_required_env('LOG_LEVEL')
        self.logging.file_path = get_required_env('LOG_FILE_PATH')
        self.logging.file_enabled = get_required_env('LOG_FILE_ENABLED', bool)
        self.logging.max_bytes = get_required_env('LOG_MAX_BYTES', int)
        self.logging.backup_count = get_required_env('LOG_BACKUP_COUNT', int)
        
        # API密钥 - 必需
        self.openai_api_key = get_required_env('OPENAI_API_KEY')
        # OpenAI API Base 可选
        self.openai_api_base = get_required_env('OPENAI_API_BASE')
        # Serper API Key 可选（如果不使用搜索功能）
        self.serper_api_key = get_optional_env('SERPER_API_KEY')
        # 提示词的语言可选
        self.prompt_language = get_optional_env('PROMPT_LANGUAGE')
    
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
                'timeout': self.pipeline.timeout,
                'use_search': self.pipeline.use_search,
                'search_model': self.pipeline.search_model,
                'search_model_infer_type': self.pipeline.search_model_infer_type,
                'search_engine': self.pipeline.search_engine,
                'search_each_query_result': self.pipeline.search_each_query_result
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
            }
        }


# 全局配置实例
_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    获取配置实例（单例模式）
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = AppConfig()
        
        _config_instance.load_from_env()
        
        # 验证配置
        if not _config_instance.validate():
            raise ValueError("配置验证失败")
        
        logger.info("配置加载完成")
    
    return _config_instance 