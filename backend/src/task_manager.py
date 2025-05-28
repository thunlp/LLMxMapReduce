"""
任务管理模块

负责任务状态管理、Redis存储和任务生命周期控制
支持Redis和SQLAlchemy两种存储方式
"""
import json
import logging
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any, Callable
from functools import wraps
import redis
from redis.exceptions import RedisError
from src.config_manager import RedisConfig


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


class BaseTaskManager(ABC):
    """任务管理器抽象基类
    
    定义了所有任务管理器必须实现的接口
    """
    
    @abstractmethod
    def create_task(self, task_id: str, params: Dict[str, Any]) -> bool:
        """创建新任务"""
        pass
    
    @abstractmethod
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          error: Optional[str] = None) -> bool:
        """更新任务状态"""
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        pass
    
    @abstractmethod
    def update_task_field(self, task_id: str, field: str, value: Any) -> bool:
        """更新任务的单个字段"""
        pass
    
    @abstractmethod
    def list_tasks(self, status: Optional[TaskStatus] = None, 
                   limit: int = 100) -> List[Dict[str, Any]]:
        """获取任务列表"""
        pass
    
    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        pass
    
    @abstractmethod
    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        pass
    
    @abstractmethod
    def cleanup_expired_tasks(self) -> int:
        """清理过期任务"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass


def with_app_context(func: Callable) -> Callable:
    """
    装饰器：自动处理Flask应用上下文
    
    这个装饰器解决了在线程中使用Flask-SQLAlchemy的核心问题：
    1. 检查是否已经在应用上下文中
    2. 如果不在，则创建新的应用上下文
    3. 确保在操作完成后正确清理上下文
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # 如果没有Flask应用实例，直接调用原函数
        if not hasattr(self, 'flask_app') or self.flask_app is None:
            return func(self, *args, **kwargs)
        
        # 检查是否已经在应用上下文中
        from flask import has_app_context
        if has_app_context():
            # 已经在应用上下文中，直接调用
            return func(self, *args, **kwargs)
        else:
            # 不在应用上下文中，创建新的上下文
            with self.flask_app.app_context():
                return func(self, *args, **kwargs)
    
    return wrapper


class PostgreSQLTaskManager(BaseTaskManager):
    """PostgreSQL任务管理器
    
    基于Flask-SQLAlchemy的任务管理器，支持在多线程环境中安全操作
    通过依赖注入Flask应用实例来解决应用上下文问题
    """
    
    def __init__(self, 
                 flask_app=None,
                 expire_time: int = 86400,  # 默认24小时过期
                 user_id: int = 1):  # 默认用户ID，用于创建任务时的关联
        """
        初始化PostgreSQL任务管理器
        
        Args:
            flask_app: Flask应用实例，用于创建应用上下文
            expire_time: 任务过期时间（秒）
            user_id: 默认用户ID
        """
        self.flask_app = flask_app
        self.expire_time = expire_time
        self.default_user_id = user_id
        
        # 验证Flask应用和数据库连接
        if flask_app:
            try:
                with flask_app.app_context():
                    from src.common_service.models import db
                    # 测试数据库连接 - 使用SQLAlchemy 2.0兼容的方式
                    with db.engine.connect() as connection:
                        connection.execute(db.text('SELECT 1'))
                    logger.info("PostgreSQL连接成功")
            except Exception as e:
                logger.error(f"PostgreSQL连接失败: {str(e)}")
                raise
        else:
            logger.warning("未提供Flask应用实例，某些功能可能无法正常工作")
    
    @with_app_context
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
            from src.common_service.models import db, Task
            
            # 计算过期时间
            expire_at = datetime.now(timezone.utc) + timedelta(seconds=self.expire_time)
            
            # 创建任务实例
            task = Task(
                task_id=task_id,
                user_id=params.get('user_id', self.default_user_id),
                status=TaskStatus.PENDING.value,
                expire_at=expire_at
            )
            
            # 设置任务参数
            task.set_params(params)
            
            # 保存到数据库
            db.session.add(task)
            db.session.commit()
            
            logger.info(f"任务创建成功: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"创建任务失败: {task_id}, error: {str(e)}")
            try:
                from src.common_service.models import db
                db.session.rollback()
            except:
                pass
            return False
    
    @with_app_context
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
            from src.common_service.models import db, Task
            
            task = Task.query.filter_by(task_id=task_id).first()
            if not task:
                logger.warning(f"任务不存在: {task_id}")
                return False
            
            # 更新状态和时间
            task.status = status.value
            task.updated_at = datetime.now(timezone.utc)
            
            if error:
                task.error = error
            
            # 根据状态设置时间字段
            if status in [TaskStatus.PROCESSING, TaskStatus.PREPARING]:
                if not task.start_time:
                    task.start_time = datetime.now(timezone.utc)
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT]:
                task.end_time = datetime.now(timezone.utc)
                
                # 计算执行时间 - 确保时区一致性
                if task.start_time:
                    # 确保start_time有时区信息
                    if task.start_time.tzinfo is None:
                        start_time_utc = task.start_time.replace(tzinfo=timezone.utc)
                    else:
                        start_time_utc = task.start_time
                    
                    execution_time = task.end_time - start_time_utc
                    task.execution_seconds = execution_time.total_seconds()
            
            db.session.commit()
            logger.info(f"任务状态更新: {task_id} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"更新任务状态失败: {task_id}, error: {str(e)}")
            try:
                from src.common_service.models import db
                db.session.rollback()
            except:
                pass
            return False
    
    @with_app_context
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典，不存在则返回None
        """
        try:
            from src.common_service.models import Task
            
            task = Task.query.filter_by(task_id=task_id).first()
            if not task:
                return None
            
            return task.to_dict()
            
        except Exception as e:
            logger.error(f"获取任务失败: {task_id}, error: {str(e)}")
            return None
    
    @with_app_context
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
            from src.common_service.models import db, Task
            
            task = Task.query.filter_by(task_id=task_id).first()
            if not task:
                logger.warning(f"任务不存在: {task_id}")
                return False
            
            # 特殊字段处理
            if field == 'params':
                task.set_params(value)
            elif field == 'result_data':
                task.set_result_data(value)
            elif hasattr(task, field):
                setattr(task, field, value)
            else:
                logger.warning(f"未知字段: {field}")
                return False
            
            task.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新任务字段失败: {task_id}.{field}, error: {str(e)}")
            try:
                from src.common_service.models import db
                db.session.rollback()
            except:
                pass
            return False
    
    @with_app_context
    def list_tasks(self, status: Optional[TaskStatus] = None, 
                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取任务列表
        
        Args:
            status: 状态筛选（可选）
            limit: 返回数量限制
            
        Returns:
            任务列表
        """
        try:
            from src.common_service.models import Task
            
            query = Task.query
            
            # 状态筛选
            if status:
                query = query.filter(Task.status == status.value)
            
            # 按创建时间倒序排序并限制数量
            tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
            
            return [task.to_dict() for task in tasks]
            
        except Exception as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            return []
    
    @with_app_context
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除是否成功
        """
        try:
            from src.common_service.models import db, Task
            
            task = Task.query.filter_by(task_id=task_id).first()
            if not task:
                logger.warning(f"任务不存在: {task_id}")
                return False
            
            db.session.delete(task)
            db.session.commit()
            logger.info(f"任务已删除: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除任务失败: {task_id}, error: {str(e)}")
            try:
                from src.common_service.models import db
                db.session.rollback()
            except:
                pass
            return False
    
    @with_app_context
    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        try:
            from src.common_service.models import Task
            
            active_statuses = [
                TaskStatus.PENDING.value, TaskStatus.PREPARING.value,
                TaskStatus.SEARCHING.value, TaskStatus.SEARCHING_WEB.value,
                TaskStatus.CRAWLING.value, TaskStatus.PROCESSING.value
            ]
            
            count = Task.query.filter(Task.status.in_(active_statuses)).count()
            return count
            
        except Exception as e:
            logger.error(f"获取活跃任务数量失败: {str(e)}")
            return 0
    
    @with_app_context
    def cleanup_expired_tasks(self) -> int:
        """清理过期任务，返回清理数量"""
        try:
            from src.common_service.models import db, Task
            
            current_time = datetime.now(timezone.utc)
            
            # 查找过期任务
            expired_tasks = Task.query.filter(Task.expire_at < current_time).all()
            expired_count = len(expired_tasks)
            
            if expired_count > 0:
                # 删除过期任务
                for task in expired_tasks:
                    db.session.delete(task)
                
                db.session.commit()
                logger.info(f"清理了 {expired_count} 个过期任务")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"清理过期任务失败: {str(e)}")
            try:
                from src.common_service.models import db
                db.session.rollback()
            except:
                pass
            return 0
    
    @with_app_context
    def health_check(self) -> bool:
        """健康检查"""
        try:
            from src.common_service.models import db
            # 执行简单查询测试数据库连接
            with db.engine.connect() as connection:
                connection.execute(db.text('SELECT 1'))
            return True
        except Exception as e:
            logger.error(f"PostgreSQL健康检查失败: {str(e)}")
            return False


class RedisTaskManager(BaseTaskManager):
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
            status: 状态筛选（可选）
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


def get_task_manager(manager_type: str = "redis", 
                    redis_config: Optional[RedisConfig] = None,
                    flask_app=None,
                    **kwargs) -> BaseTaskManager:
    """
    获取任务管理器实例（单例模式）
    
    Args:
        manager_type: 管理器类型 ("redis" 或 "postgresql")
        redis_config: Redis配置（当manager_type为"redis"时使用）
        flask_app: Flask应用实例（当manager_type为"postgresql"时使用）
        **kwargs: 其他配置参数
        
    Returns:
        BaseTaskManager实例
    """
    global _task_manager_instance
    
    if _task_manager_instance is None:
        if manager_type == "redis":
            if redis_config is None:
                raise ValueError("Redis模式下配置不能为空")
            _task_manager_instance = RedisTaskManager(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.db,
                password=redis_config.password,
                key_prefix=redis_config.key_prefix,
                expire_time=redis_config.expire_time
            )
        elif manager_type == "postgresql":
            _task_manager_instance = PostgreSQLTaskManager(
                flask_app=flask_app,
                expire_time=kwargs.get('expire_time', 86400),
                user_id=kwargs.get('user_id', 1)
            )
        else:
            raise ValueError(f"不支持的TaskManager类型: {manager_type}")
    
    return _task_manager_instance


def reset_task_manager():
    """重置任务管理器实例（主要用于测试）"""
    global _task_manager_instance
    _task_manager_instance = None 