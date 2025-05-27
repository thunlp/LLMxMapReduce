"""
数据库管理模块

提供MongoDB连接和操作功能
"""

from .mongo_manager import MongoManager, get_mongo_manager

__all__ = ['MongoManager', 'get_mongo_manager'] 