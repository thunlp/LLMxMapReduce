"""
任务管理模块

负责任务状态管理、Redis存储和任务生命周期控制
"""
import json
import logging
from enum import Enum
from datetime import datetime
from typing import Dict, Optional, List, Any
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"              # 待处理
    PREPARING = "preparing"          # 准备中
    SEARCHING = "searching"          # 生成查询中
    SEARCHING_WEB = "searching_web"  # 搜索网页中
    CRAWLING = "crawling"           # 爬取内容中
    PROCESSING = "processing"       # 处理中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"              # 失败
    TIMEOUT = "timeout"            # 超时


class RedisTaskManager:
    """Redis任务管理器
    
    负责任务的创建、更新、查询和删除操作
    使用Redis作为持久化存储，支持分布式部署
    """
    
    def __init__(self, 
                 host: str = 'localhost',
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 key_prefix: str = 'llm_task:',
                 expire_time: int = 86400):  # 默认24小时过期
        """
        初始化Redis任务管理器
        
        Args:
            host: Redis主机地址
            port: Redis端口
            db: Redis数据库索引
            password: Redis密码
            key_prefix: 键前缀
            expire_time: 任务过期时间（秒）
        """
        self.key_prefix = key_prefix
        self.expire_time = expire_time
        
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                max_connections=50,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            # 测试redis连接
            self.redis_client.ping()
            logger.info(f"Redis连接成功: {host}:{port}")
        except RedisError as e:
            logger.error(f"Redis连接失败: {str(e)}")
            raise
    
    def _get_task_key(self, task_id: str) -> str:
        """获取任务的Redis键"""
        return f"{self.key_prefix}{task_id}"
    
    def create_task(self, task_id: str, params: Dict[str, Any]) -> bool:
        """
        创建新任务
        
        Args:
            task_id: 任务ID
            params: 任务参数
            
        Returns:
            创建是否成功
        """
        try:
            task_data = {
                'id': task_id,
                'status': TaskStatus.PENDING.value,
                'created_at': datetime.now().isoformat(),
                'params': json.dumps(params),
                'updated_at': datetime.now().isoformat()
            }
            
            key = self._get_task_key(task_id)
            # 使用pipeline提高性能
            with self.redis_client.pipeline() as pipe:
                pipe.hset(key, mapping=task_data)
                pipe.expire(key, self.expire_time)
                pipe.execute()
            
            logger.info(f"任务创建成功: {task_id}")
            return True
            
        except RedisError as e:
            logger.error(f"创建任务失败: {task_id}, error: {str(e)}")
            return False
    
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          error: Optional[str] = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            error: 错误信息（可选）
            
        Returns:
            更新是否成功
        """
        try:
            key = self._get_task_key(task_id)
            update_data = {
                'status': status.value,
                'updated_at': datetime.now().isoformat()
            }
            
            if error:
                update_data['error'] = error
            
            # 特殊状态处理
            if status == TaskStatus.COMPLETED:
                update_data['end_time'] = datetime.now().isoformat()
            elif status == TaskStatus.PREPARING:
                update_data['start_time'] = datetime.now().isoformat()
                
            self.redis_client.hset(key, mapping=update_data)
            logger.info(f"任务状态更新: {task_id} -> {status.value}")
            return True
            
        except RedisError as e:
            logger.error(f"更新任务状态失败: {task_id}, error: {str(e)}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典，不存在则返回None
        """
        try:
            key = self._get_task_key(task_id)
            task_data = self.redis_client.hgetall(key)
            
            if not task_data:
                return None
            
            # 解析JSON字段
            if 'params' in task_data:
                task_data['params'] = json.loads(task_data['params'])
            
            # 计算执行时间
            if 'start_time' in task_data and 'end_time' in task_data:
                start = datetime.fromisoformat(task_data['start_time'])
                end = datetime.fromisoformat(task_data['end_time'])
                execution_time = end - start
                task_data['execution_time'] = str(execution_time)
                task_data['execution_seconds'] = execution_time.total_seconds()
            
            return task_data
            
        except RedisError as e:
            logger.error(f"获取任务失败: {task_id}, error: {str(e)}")
            return None
    
    def update_task_field(self, task_id: str, field: str, value: Any) -> bool:
        """
        更新任务的单个字段
        
        Args:
            task_id: 任务ID
            field: 字段名
            value: 字段值
            
        Returns:
            更新是否成功
        """
        try:
            key = self._get_task_key(task_id)
            # 如果值是字典或列表，转换为JSON
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            
            self.redis_client.hset(key, field, value)
            self.redis_client.hset(key, 'updated_at', datetime.now().isoformat())
            return True
            
        except RedisError as e:
            logger.error(f"更新任务字段失败: {task_id}.{field}, error: {str(e)}")
            return False
    
    def list_tasks(self, status: Optional[TaskStatus] = None, 
                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取任务列表
        
        Args:
            status: 筛选状态（可选）
            limit: 返回数量限制
            
        Returns:
            任务列表
        """
        try:
            # 获取所有任务键
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            tasks = []
            for key in keys[:limit]:
                task_id = key.replace(self.key_prefix, '')
                task = self.get_task(task_id)
                if task:
                    # 状态筛选
                    if status and task.get('status') != status.value:
                        continue
                    tasks.append(task)
            
            # 按创建时间倒序排序
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except RedisError as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            return []
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除是否成功
        """
        try:
            key = self._get_task_key(task_id)
            result = self.redis_client.delete(key)
            if result:
                logger.info(f"任务已删除: {task_id}")
            return bool(result)
            
        except RedisError as e:
            logger.error(f"删除任务失败: {task_id}, error: {str(e)}")
            return False
    
    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        active_statuses = [
            TaskStatus.PENDING, TaskStatus.PREPARING,
            TaskStatus.SEARCHING, TaskStatus.SEARCHING_WEB,
            TaskStatus.CRAWLING, TaskStatus.PROCESSING
        ]
        
        count = 0
        for status in active_statuses:
            tasks = self.list_tasks(status=status)
            count += len(tasks)
        
        return count
    
    def cleanup_expired_tasks(self) -> int:
        """清理过期任务，返回清理数量"""
        # Redis会自动处理过期，这里只是统计
        try:
            pattern = f"{self.key_prefix}*"
            all_keys = self.redis_client.keys(pattern)
            
            expired_count = 0
            for key in all_keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -2:  # 键不存在
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"清理了 {expired_count} 个过期任务")
            
            return expired_count
            
        except RedisError as e:
            logger.error(f"清理过期任务失败: {str(e)}")
            return 0
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.redis_client.ping()
            return True
        except RedisError:
            return False


# 创建全局任务管理器实例（单例模式）
_task_manager_instance = None


def get_task_manager(redis_config: Optional[Dict[str, Any]] = None) -> RedisTaskManager:
    """
    获取任务管理器实例（单例模式）
    
    Args:
        redis_config: Redis配置字典
        
    Returns:
        RedisTaskManager实例
    """
    global _task_manager_instance
    
    if _task_manager_instance is None:
        if redis_config is None:
            raise ValueError("初始化阶段Redis配置字典不能为空")
        _task_manager_instance = RedisTaskManager(**redis_config)
    
    return _task_manager_instance 