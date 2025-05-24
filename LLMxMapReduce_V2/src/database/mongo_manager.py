"""
MongoDB数据库管理模块

提供以下功能：
1. MongoDB连接池管理
2. Survey数据的CRUD操作
3. 错误处理和重试机制
4. 索引管理
"""

import os
import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)


class MongoManager:
    """MongoDB管理类，线程安全的单例模式"""
    
    _instance = None
    _instance_lock = threading.Lock()  # 用于单例创建的锁
    _connection_lock = threading.Lock()  # 用于连接操作的锁
    _client = None
    _db = None
    
    def __new__(cls, *args, **kwargs):
        # 双重检查锁定（Double-Checked Locking）模式
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super(MongoManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, 
                 connection_string: str = None,
                 database_name: str = "llm_mapreduce",
                 collection_name: str = "surveys"):
        
        # 使用锁保护初始化过程
        with self._instance_lock:
            if hasattr(self, '_initialized'):
                return
            
            self.connection_string = connection_string or os.environ.get(
                'MONGODB_CONNECTION_STRING', 
                'mongodb://localhost:27017/'
            )
            self.database_name = database_name
            self.collection_name = collection_name
            self.max_retries = 3
            self.retry_delay = 1
            
            self._initialized = True
            logger.info(f"初始化MongoDB管理器: {self.database_name}.{self.collection_name}")
    
    def connect(self) -> bool:
        """建立MongoDB连接 - 线程安全版本"""
        try:
            # 使用连接锁保护整个连接过程
            with self._connection_lock:
                if self._client is None:
                    logger.info(f"连接到MongoDB: {self.connection_string}")
                    self._client = MongoClient(
                        self.connection_string,
                        serverSelectionTimeoutMS=5000,  # 5秒超时
                        connectTimeoutMS=5000,
                        maxPoolSize=50,
                        minPoolSize=5
                    )
                    
                    # 测试连接
                    self._client.admin.command('ping')
                    logger.info("MongoDB连接成功")
                
                if self._db is None:
                    self._db = self._client[self.database_name]
                    self._create_indexes()
            
            return True
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB连接失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"MongoDB连接异常: {str(e)}")
            return False
    
    def _create_indexes(self):
        """创建必要的索引"""
        try:
            collection = self._db[self.collection_name]
            
            # 为task_id创建唯一索引
            collection.create_index("task_id", unique=True)
            
            # 为title创建索引
            collection.create_index("title")
            
            # 为created_at创建索引（用于时间范围查询）
            collection.create_index([("created_at", ASCENDING)])
            
            # 为status创建索引
            collection.create_index("status")
            
            logger.info("MongoDB索引创建完成")
            
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
    
    def disconnect(self):
        """断开MongoDB连接 - 线程安全版本"""
        with self._connection_lock:
            if self._client:
                self._client.close()
                self._client = None
                self._db = None
                logger.info("MongoDB连接已断开")
    
    def _retry_operation(self, operation, *args, **kwargs):
        """重试机制装饰器"""
        for attempt in range(self.max_retries):
            try:
                if not self.connect():
                    raise ConnectionFailure("无法连接到MongoDB")
                
                return operation(*args, **kwargs)
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"操作失败，已重试{self.max_retries}次: {str(e)}")
                    raise
                else:
                    logger.warning(f"操作失败，第{attempt + 1}次重试: {str(e)}")
                    time.sleep(self.retry_delay * (attempt + 1))
    
    def save_survey(self, task_id: str, survey_data: Dict[str, Any]) -> bool:
        """保存survey数据"""
        
        def _save_operation():
            collection = self._db[self.collection_name]
            
            # 确保survey_data中包含正确的task_id
            survey_data_with_task_id = survey_data.copy()
            survey_data_with_task_id["task_id"] = task_id
            
            document = {
                "task_id": task_id,
                "title": survey_data.get("title", ""),
                "survey_data": survey_data_with_task_id,  # 使用包含task_id的副本
                "created_at": datetime.now(),
                "status": "completed",
                "metadata": {
                    "cite_ratio": survey_data.get("cite_ratio", 0),
                    "content_length": len(survey_data.get("content", "")),
                    "references_count": len(survey_data.get("papers", []))
                }
            }
            
            # 使用upsert模式，如果task_id已存在则更新
            result = collection.replace_one(
                {"task_id": task_id},
                document,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                logger.info(f"Survey保存成功: task_id={task_id}, title={survey_data.get('title', '')}")
                return True
            else:
                logger.warning(f"Survey保存未发生变化: task_id={task_id}")
                return False
        
        try:
            return self._retry_operation(_save_operation)
        except Exception as e:
            logger.error(f"保存Survey失败: task_id={task_id}, error={str(e)}")
            return False
    
    def get_survey(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据task_id获取survey数据"""
        
        def _get_operation():
            collection = self._db[self.collection_name]
            result = collection.find_one({"task_id": task_id})
            
            if result:
                logger.debug(f"找到Survey: task_id={task_id}")
                return result
            else:
                logger.debug(f"未找到Survey: task_id={task_id}")
                return None
        
        try:
            return self._retry_operation(_get_operation)
        except Exception as e:
            logger.error(f"获取Survey失败: task_id={task_id}, error={str(e)}")
            return None
    
    def get_survey_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """根据标题获取survey数据"""
        
        def _get_operation():
            collection = self._db[self.collection_name]
            result = collection.find_one({"title": title})
            
            if result:
                logger.debug(f"根据标题找到Survey: title={title}")
                return result
            else:
                logger.debug(f"根据标题未找到Survey: title={title}")
                return None
        
        try:
            return self._retry_operation(_get_operation)
        except Exception as e:
            logger.error(f"根据标题获取Survey失败: title={title}, error={str(e)}")
            return None
    
    def list_surveys(self, 
                    status: str = None, 
                    limit: int = 100, 
                    skip: int = 0,
                    sort_by: str = "created_at",
                    sort_order: int = -1) -> List[Dict[str, Any]]:
        """获取survey列表"""
        
        def _list_operation():
            collection = self._db[self.collection_name]
            
            query = {}
            if status:
                query["status"] = status
            
            cursor = collection.find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
            
            results = list(cursor)
            logger.debug(f"获取到{len(results)}个Survey记录")
            return results
        
        try:
            return self._retry_operation(_list_operation)
        except Exception as e:
            logger.error(f"获取Survey列表失败: error={str(e)}")
            return []
    
    def update_survey_status(self, task_id: str, status: str) -> bool:
        """更新survey状态"""
        
        def _update_operation():
            collection = self._db[self.collection_name]
            result = collection.update_one(
                {"task_id": task_id},
                {"$set": {"status": status, "updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Survey状态更新成功: task_id={task_id}, status={status}")
                return True
            else:
                logger.warning(f"Survey状态更新无变化: task_id={task_id}, status={status}")
                return False
        
        try:
            return self._retry_operation(_update_operation)
        except Exception as e:
            logger.error(f"更新Survey状态失败: task_id={task_id}, error={str(e)}")
            return False
    
    def delete_survey(self, task_id: str) -> bool:
        """删除survey"""
        
        def _delete_operation():
            collection = self._db[self.collection_name]
            result = collection.delete_one({"task_id": task_id})
            
            if result.deleted_count > 0:
                logger.info(f"Survey删除成功: task_id={task_id}")
                return True
            else:
                logger.warning(f"Survey删除失败，记录不存在: task_id={task_id}")
                return False
        
        try:
            return self._retry_operation(_delete_operation)
        except Exception as e:
            logger.error(f"删除Survey失败: task_id={task_id}, error={str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        
        def _stats_operation():
            collection = self._db[self.collection_name]
            
            total_count = collection.count_documents({})
            completed_count = collection.count_documents({"status": "completed"})
            failed_count = collection.count_documents({"status": "failed"})
            
            # 获取最近的surveys
            recent_surveys = list(collection.find({}, {"task_id": 1, "title": 1, "created_at": 1, "status": 1})
                                .sort("created_at", -1).limit(10))
            
            return {
                "total_surveys": total_count,
                "completed_surveys": completed_count,
                "failed_surveys": failed_count,
                "success_rate": completed_count / total_count if total_count > 0 else 0,
                "recent_surveys": recent_surveys
            }
        
        try:
            return self._retry_operation(_stats_operation)
        except Exception as e:
            logger.error(f"获取统计信息失败: error={str(e)}")
            return {
                "total_surveys": 0,
                "completed_surveys": 0, 
                "failed_surveys": 0,
                "success_rate": 0,
                "recent_surveys": []
            }
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self.connect():
                return False
            
            # 尝试执行一个简单的操作
            self._client.admin.command('ping')
            return True
            
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return False


# 全局实例
mongo_manager = MongoManager() 