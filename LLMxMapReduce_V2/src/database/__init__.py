"""
数据库管理模块

提供MongoDB连接和操作功能
"""

from .mongo_manager import MongoManager, mongo_manager

__all__ = ['MongoManager', 'mongo_manager'] 