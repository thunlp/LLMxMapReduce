import unittest
import time
from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.task_manager import RedisTaskManager, TaskStatus
import json

class TestRedisTaskManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """在所有测试前执行一次"""
        # 使用不同的数据库索引以避免干扰生产数据
        cls.redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 15,  # 通常15是测试用的数据库
            'key_prefix': 'test_task:',
            'expire_time': 60  # 1分钟过期时间，便于测试
        }
        cls.task_manager = RedisTaskManager(**cls.redis_config)
        
        # 确保测试数据库是空的
        cls._cleanup_test_database()

    @classmethod
    def tearDownClass(cls):
        """在所有测试后执行一次"""
        cls._cleanup_test_database()

    @classmethod
    def _cleanup_test_database(cls):
        """清理测试数据库"""
        keys = cls.task_manager.redis_client.keys(f"{cls.redis_config['key_prefix']}*")
        if keys:
            cls.task_manager.redis_client.delete(*keys)

    def setUp(self):
        """在每个测试前执行"""
        self.test_task_id = f"test_task_{int(time.time())}"
        self.test_params = {"query": "test query", "user_id": 123}

    def tearDown(self):
        """在每个测试后执行"""
        # 删除测试创建的任务
        self.task_manager.delete_task(self.test_task_id)

    def test_01_redis_connection(self):
        """测试Redis连接是否正常"""
        self.assertTrue(self.task_manager.health_check())

    def test_02_create_task(self):
        """测试创建任务"""
        # 创建任务
        result = self.task_manager.create_task(self.test_task_id, self.test_params)
        self.assertTrue(result)
        
        # 验证任务存在
        task = self.task_manager.get_task(self.test_task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task['id'], self.test_task_id)
        self.assertEqual(task['status'], TaskStatus.PENDING.value)
        self.assertEqual(task['params'], self.test_params)
        
        # 验证创建时间和更新时间
        self.assertIn('created_at', task)
        self.assertIn('updated_at', task)
        created_at = datetime.fromisoformat(task['created_at'])
        self.assertLessEqual(created_at, datetime.now())

    def test_03_update_task_status(self):
        """测试更新任务状态"""
        # 先创建任务
        self.task_manager.create_task(self.test_task_id, self.test_params)
        
        # 更新状态为PREPARING
        result = self.task_manager.update_task_status(
            self.test_task_id, TaskStatus.PREPARING)
        self.assertTrue(result)
        
        # 验证状态更新
        task = self.task_manager.get_task(self.test_task_id)
        self.assertEqual(task['status'], TaskStatus.PREPARING.value)
        self.assertIn('start_time', task)
        
        # 更新状态为COMPLETED
        result = self.task_manager.update_task_status(
            self.test_task_id, TaskStatus.COMPLETED)
        self.assertTrue(result)
        
        # 验证状态和结束时间
        task = self.task_manager.get_task(self.test_task_id)
        self.assertEqual(task['status'], TaskStatus.COMPLETED.value)
        self.assertIn('end_time', task)
        self.assertIn('execution_time', task)
        self.assertIn('execution_seconds', task)

    def test_04_update_task_with_error(self):
        """测试更新任务状态时添加错误信息"""
        # 先创建任务
        self.task_manager.create_task(self.test_task_id, self.test_params)
        
        # 更新状态为FAILED并添加错误信息
        error_msg = "Test error message"
        result = self.task_manager.update_task_status(
            self.test_task_id, TaskStatus.FAILED, error_msg)
        self.assertTrue(result)
        
        # 验证错误信息
        task = self.task_manager.get_task(self.test_task_id)
        self.assertEqual(task['status'], TaskStatus.FAILED.value)
        self.assertEqual(task['error'], error_msg)

    def test_05_update_task_field(self):
        """测试更新任务的单个字段"""
        # 先创建任务
        self.task_manager.create_task(self.test_task_id, self.test_params)
        
        # 更新单个字段
        test_result = {"result": "success", "data": [1, 2, 3]}
        result = self.task_manager.update_task_field(
            self.test_task_id, "result", test_result)
        self.assertTrue(result)
        
        # 验证字段更新
        task = self.task_manager.get_task(self.test_task_id)
        task_result = json.loads(task['result'])
        self.assertEqual(task_result, test_result)
        
        # 验证更新时间已更新
        updated_at = datetime.fromisoformat(task['updated_at'])
        self.assertLessEqual(updated_at, datetime.now())

    def test_06_list_tasks(self):
        """测试获取任务列表"""
        # 创建几个测试任务
        task_ids = [f"list_test_{i}_{int(time.time())}" for i in range(3)]
        for task_id in task_ids:
            self.task_manager.create_task(task_id, self.test_params)
            self.task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
        
        # 获取所有任务
        all_tasks = self.task_manager.list_tasks()
        self.assertGreaterEqual(len(all_tasks), 3)
        
        # 验证最近创建的任务在列表前面
        task_ids_in_list = [task['id'] for task in all_tasks[:3]]
        self.assertTrue(all(task_id in task_ids_in_list for task_id in task_ids))
        
        # 按状态筛选
        processing_tasks = self.task_manager.list_tasks(status=TaskStatus.PROCESSING)
        self.assertGreaterEqual(len(processing_tasks), 3)
        for task in processing_tasks:
            self.assertEqual(task['status'], TaskStatus.PROCESSING.value)
        
        # 清理测试任务
        for task_id in task_ids:
            self.task_manager.delete_task(task_id)

    def test_07_delete_task(self):
        """测试删除任务"""
        # 先创建任务
        self.task_manager.create_task(self.test_task_id, self.test_params)
        
        # 验证任务存在
        task = self.task_manager.get_task(self.test_task_id)
        self.assertIsNotNone(task)
        
        # 删除任务
        result = self.task_manager.delete_task(self.test_task_id)
        self.assertTrue(result)
        
        # 验证任务已删除
        task = self.task_manager.get_task(self.test_task_id)
        self.assertIsNone(task)

    def test_08_get_active_task_count(self):
        """测试获取活跃任务数量"""
        # 创建几个活跃任务
        active_task_ids = [f"active_test_{i}_{int(time.time())}" for i in range(2)]
        for task_id in active_task_ids:
            self.task_manager.create_task(task_id, self.test_params)
            self.task_manager.update_task_status(task_id, TaskStatus.SEARCHING)
        
        # 创建一个非活跃任务
        completed_task_id = f"completed_test_{int(time.time())}"
        self.task_manager.create_task(completed_task_id, self.test_params)
        self.task_manager.update_task_status(completed_task_id, TaskStatus.COMPLETED)
        
        # 获取活跃任务数量
        active_count = self.task_manager.get_active_task_count()
        self.assertGreaterEqual(active_count, 2)
        
        # 清理测试任务
        for task_id in active_task_ids + [completed_task_id]:
            self.task_manager.delete_task(task_id)

    def test_09_task_expiration(self):
        """测试任务过期"""
        # 创建一个短期过期的任务
        temp_task_id = f"expire_test_{int(time.time())}"
        temp_manager = RedisTaskManager(
            **{**self.redis_config, 'expire_time': 2})  # 2秒过期
        
        temp_manager.create_task(temp_task_id, self.test_params)
        
        # 验证任务存在
        task = temp_manager.get_task(temp_task_id)
        self.assertIsNotNone(task)
        
        # 等待过期
        time.sleep(3)
        
        # 验证任务已过期
        task = temp_manager.get_task(temp_task_id)
        self.assertIsNone(task)

    def test_10_cleanup_expired_tasks(self):
        """测试清理过期任务"""
        # 这个测试主要验证方法是否能正常执行
        # 实际过期由Redis处理，我们无法精确控制测试环境
        count = self.task_manager.cleanup_expired_tasks()
        self.assertIsInstance(count, int)


if __name__ == '__main__':
    unittest.main(failfast=True)