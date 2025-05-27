"""
API服务完整流程测试

测试api_service.py中的所有API端点，包括：
- Pipeline任务管理
- 任务状态查询
- 输出结果获取
- 数据库操作
- 健康检查
"""
import unittest
import json
import time
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from src.api_service import api_bp, set_pipeline_manager
from src.task_manager import TaskStatus, RedisTaskManager
from src.pipeline_processor import PipelineTaskManager


class TestAPIService(unittest.TestCase):
    """API服务测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        # 创建Flask测试应用
        cls.app = Flask(__name__)
        cls.app.register_blueprint(api_bp)
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        
        # 模拟Redis配置
        cls.redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 15,  # 测试数据库
            'key_prefix': 'test_api:',
            'expire_time': 300
        }
        
        # 初始化任务管理器
        try:
            cls.task_manager = RedisTaskManager(**cls.redis_config)
            cls._cleanup_test_database()
        except Exception as e:
            print(f"警告：Redis连接失败，将使用模拟对象: {e}")
            cls.task_manager = None
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        if cls.task_manager:
            cls._cleanup_test_database()
    
    @classmethod
    def _cleanup_test_database(cls):
        """清理测试数据库"""
        if cls.task_manager:
            keys = cls.task_manager.redis_client.keys(f"{cls.redis_config['key_prefix']}*")
            if keys:
                cls.task_manager.redis_client.delete(*keys)
    
    def setUp(self):
        """每个测试前的准备"""
        self.test_task_id = f"test_task_{int(time.time())}"
        self.test_params = {
            "topic": "人工智能在医疗领域的应用",
            "description": "研究AI在医疗诊断、药物发现等方面的应用",
            "output_file": f"test_output_{int(time.time())}.json",
            "block_count": 5,
            "data_num": 10,
            "top_n": 20
        }
        
        # 模拟Pipeline任务管理器
        self.mock_pipeline_manager = Mock(spec=PipelineTaskManager)
        self.mock_global_pipeline = Mock()
        self.mock_pipeline_manager.global_pipeline = self.mock_global_pipeline
        
        # 设置Pipeline管理器
        set_pipeline_manager(self.mock_pipeline_manager)
    
    def tearDown(self):
        """每个测试后的清理"""
        if self.task_manager:
            self.task_manager.delete_task(self.test_task_id)
    
    @patch('src.api_service.get_task_manager')
    def test_01_submit_task_success(self, mock_get_task_manager):
        """测试成功提交任务"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟任务数据
        mock_task = {
            'id': self.test_task_id,
            'status': TaskStatus.PENDING.value,
            'params': self.test_params,
            'original_topic': self.test_params['topic'],
            'expected_survey_title': f"关于{self.test_params['topic']}的综述"
        }
        mock_task_manager.get_task.return_value = mock_task
        
        # 模拟Pipeline管理器提交任务
        self.mock_pipeline_manager.submit_task.return_value = self.test_task_id
        
        # 发送请求
        response = self.client.post('/api/task/submit', 
                                  json=self.test_params,
                                  content_type='application/json')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['task_id'], self.test_task_id)
        self.assertIn('message', data)
        self.assertIn('output_file', data)
        
        # 验证调用
        self.mock_pipeline_manager.submit_task.assert_called_once_with(self.test_params)
        mock_task_manager.get_task.assert_called_once_with(self.test_task_id)
    
    def test_02_submit_task_no_manager(self):
        """测试Pipeline管理器未初始化的情况"""
        # 清除Pipeline管理器
        set_pipeline_manager(None)
        
        # 发送请求
        response = self.client.post('/api/task/submit', 
                                  json=self.test_params,
                                  content_type='application/json')
        
        # 验证响应
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Pipeline管理器未初始化', data['error'])
        
        # 恢复Pipeline管理器
        set_pipeline_manager(self.mock_pipeline_manager)
    
    @patch('src.api_service.get_task_manager')
    def test_03_get_task_status_success(self, mock_get_task_manager):
        """测试成功获取任务状态"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟任务数据
        mock_task = {
            'id': self.test_task_id,
            'status': TaskStatus.PROCESSING.value,
            'params': self.test_params,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        mock_task_manager.get_task.return_value = mock_task
        
        # 发送请求
        response = self.client.get(f'/api/task/{self.test_task_id}')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['task']['id'], self.test_task_id)
        self.assertEqual(data['task']['status'], TaskStatus.PROCESSING.value)
    
    @patch('src.api_service.get_task_manager')
    def test_04_get_task_status_not_found(self, mock_get_task_manager):
        """测试获取不存在的任务状态"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        mock_task_manager.get_task.return_value = None
        
        # 发送请求
        response = self.client.get(f'/api/task/nonexistent_task')
        
        # 验证响应
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('任务不存在', data['error'])
    
    @patch('src.api_service.get_task_manager')
    def test_05_get_pipeline_status(self, mock_get_task_manager):
        """测试获取Pipeline状态"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟任务数据
        mock_task = {
            'id': self.test_task_id,
            'status': TaskStatus.PROCESSING.value
        }
        mock_task_manager.get_task.return_value = mock_task
        
        # 模拟Pipeline状态
        self.mock_global_pipeline.is_start = True
        
        # 创建更完整的节点Mock对象
        encode_node = Mock()
        encode_node.is_start = True
        encode_node.src_queue = Mock()
        encode_node.src_queue.qsize.return_value = 5
        encode_node.src_queue.maxsize = 100
        encode_node.executing_data_queue = ['task1', 'task2']  # 模拟执行队列
        encode_node.worker_num = 2
        
        hidden_node = Mock()
        hidden_node.is_start = True
        hidden_node.src_queue = Mock()
        hidden_node.src_queue.qsize.return_value = 3
        hidden_node.src_queue.maxsize = 50
        hidden_node.executing_data_queue = ['task3']
        hidden_node.worker_num = 1
        
        decode_node = Mock()
        decode_node.is_start = False
        decode_node.src_queue = Mock()
        decode_node.src_queue.qsize.return_value = 0
        decode_node.src_queue.maxsize = 10
        decode_node.executing_data_queue = []
        decode_node.worker_num = 1
        
        self.mock_global_pipeline.all_nodes = {
            'encode_pipeline': encode_node,
            'hidden_pipeline': hidden_node,
            'decode_pipeline': decode_node
        }
        
        # 发送请求
        response = self.client.get(f'/api/task/{self.test_task_id}/pipeline_status')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['task_id'], self.test_task_id)
        self.assertTrue(data['pipeline_running'])
        self.assertEqual(len(data['nodes']), 3)
    
    @patch('src.api_service.get_task_manager')
    def test_06_get_global_pipeline_status(self, mock_get_task_manager):
        """测试获取全局Pipeline状态"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        mock_task_manager.get_active_task_count.return_value = 2
        mock_task_manager.list_tasks.return_value = [{'id': '1'}, {'id': '2'}, {'id': '3'}]
        
        # 模拟Pipeline状态
        self.mock_global_pipeline.is_start = True
        
        # 创建更完整的节点Mock对象
        encode_node = Mock()
        encode_node.is_start = True
        encode_node.src_queue = Mock()
        encode_node.src_queue.qsize.return_value = 2
        encode_node.src_queue.maxsize = 10
        encode_node.executing_data_queue = ['task1']
        encode_node.worker_num = 1
        
        hidden_node = Mock()
        hidden_node.is_start = True
        hidden_node.src_queue = Mock()
        hidden_node.src_queue.qsize.return_value = 1
        hidden_node.src_queue.maxsize = 10
        hidden_node.executing_data_queue = []
        hidden_node.worker_num = 2
        
        self.mock_global_pipeline.all_nodes = {
            'encode_pipeline': encode_node,
            'hidden_pipeline': hidden_node
        }
        
        # 发送请求
        response = self.client.get('/api/global_pipeline_status')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['pipeline_initialized'])
        self.assertTrue(data['pipeline_running'])
        self.assertEqual(data['active_tasks_count'], 2)
        self.assertEqual(data['total_tasks_count'], 3)
    
    @patch('src.api_service.get_task_manager')
    def test_07_list_tasks(self, mock_get_task_manager):
        """测试获取任务列表"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟任务列表
        mock_tasks = [
            {'id': 'task1', 'status': TaskStatus.COMPLETED.value},
            {'id': 'task2', 'status': TaskStatus.PROCESSING.value},
            {'id': 'task3', 'status': TaskStatus.PENDING.value}
        ]
        mock_task_manager.list_tasks.return_value = mock_tasks
        
        # 测试获取所有任务
        response = self.client.get('/api/tasks')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['tasks']), 3)
        self.assertEqual(data['count'], 3)
        
        # 测试按状态筛选
        response = self.client.get('/api/tasks?status=processing&limit=10')
        self.assertEqual(response.status_code, 200)
        
        # 测试无效状态
        response = self.client.get('/api/tasks?status=invalid_status')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('无效的状态值', data['error'])
    
    @patch('src.api_service.mongo_manager')
    @patch('src.api_service.get_task_manager')
    def test_08_get_task_output_from_database(self, mock_get_task_manager, mock_mongo_manager):
        """测试从数据库获取任务输出"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟已完成的任务
        mock_task = {
            'id': self.test_task_id,
            'status': TaskStatus.COMPLETED.value,
            'params': self.test_params
        }
        mock_task_manager.get_task.return_value = mock_task
        
        # 模拟数据库返回的综述数据
        mock_survey_data = {
            'title': '人工智能在医疗领域的应用综述',
            'abstract': '本文综述了AI在医疗领域的最新进展...',
            'sections': [
                {'title': '引言', 'content': '人工智能技术...'},
                {'title': '应用领域', 'content': '医疗诊断、药物发现...'}
            ]
        }
        
        mock_survey = {
            'survey_data': mock_survey_data,
            'created_at': datetime.now().isoformat(),
            'title': '人工智能在医疗领域的应用综述',
            'status': 'completed'
        }
        mock_mongo_manager.get_survey.return_value = mock_survey
        
        # 发送请求
        response = self.client.get(f'/api/output/{self.test_task_id}')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'database')
        self.assertIn('content', data)
        self.assertIn('metadata', data)
        
        # 验证内容是JSON格式的综述数据
        content_data = json.loads(data['content'])
        self.assertEqual(content_data['title'], mock_survey_data['title'])
    
    @patch('src.api_service.mongo_manager', None)
    @patch('src.api_service.get_task_manager')
    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    def test_09_get_task_output_from_file(self, mock_exists, mock_open, mock_get_task_manager):
        """测试从文件获取任务输出"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟已完成的任务
        mock_task = {
            'id': self.test_task_id,
            'status': TaskStatus.COMPLETED.value,
            'params': self.test_params
        }
        mock_task_manager.get_task.return_value = mock_task
        
        # 模拟文件存在
        mock_exists.return_value = True
        
        # 模拟文件内容
        mock_file_content = json.dumps({
            'title': '测试综述',
            'content': '这是测试内容'
        }, ensure_ascii=False, indent=2)
        
        mock_file = Mock()
        mock_file.read.return_value = mock_file_content
        mock_open.return_value.__enter__.return_value = mock_file
        
        # 发送请求
        response = self.client.get(f'/api/output/{self.test_task_id}')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'file')
        self.assertEqual(data['content'], mock_file_content)
        self.assertIn('output_file', data)
    
    @patch('src.api_service.get_task_manager')
    def test_10_get_task_output_not_completed(self, mock_get_task_manager):
        """测试获取未完成任务的输出"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 模拟未完成的任务
        mock_task = {
            'id': self.test_task_id,
            'status': TaskStatus.PROCESSING.value,
            'params': self.test_params
        }
        mock_task_manager.get_task.return_value = mock_task
        
        # 发送请求
        response = self.client.get(f'/api/output/{self.test_task_id}')
        
        # 验证响应
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('任务尚未完成', data['error'])
    
    @patch('src.api_service.mongo_manager')
    def test_11_database_stats(self, mock_mongo_manager):
        """测试获取数据库统计信息"""
        # 模拟数据库统计
        mock_stats = {
            'total_surveys': 150,
            'completed_surveys': 120,
            'failed_surveys': 5,
            'database_size': '2.5GB'
        }
        mock_mongo_manager.get_stats.return_value = mock_stats
        
        # 发送请求
        response = self.client.get('/api/database/stats')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['stats'], mock_stats)
    
    @patch('src.api_service.mongo_manager', None)
    def test_12_database_stats_unavailable(self):
        """测试数据库不可用时的统计信息"""
        # 发送请求
        response = self.client.get('/api/database/stats')
        
        # 验证响应
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('数据库不可用', data['error'])
    
    @patch('src.api_service.mongo_manager')
    def test_13_database_health_check(self, mock_mongo_manager):
        """测试数据库健康检查"""
        # 测试健康状态
        mock_mongo_manager.health_check.return_value = True
        response = self.client.get('/api/database/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'healthy')
        
        # 测试不健康状态
        mock_mongo_manager.health_check.return_value = False
        response = self.client.get('/api/database/health')
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data['status'], 'unhealthy')
    
    @patch('src.api_service.get_task_manager')
    def test_14_delete_task(self, mock_get_task_manager):
        """测试删除任务"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        
        # 测试成功删除
        mock_task_manager.delete_task.return_value = True
        response = self.client.delete(f'/api/task/{self.test_task_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('已删除', data['message'])
        
        # 测试删除失败
        mock_task_manager.delete_task.return_value = False
        response = self.client.delete(f'/api/task/{self.test_task_id}')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    @patch('src.api_service.mongo_manager')
    @patch('src.api_service.get_task_manager')
    def test_15_health_check(self, mock_get_task_manager, mock_mongo_manager):
        """测试服务健康检查"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        mock_task_manager.health_check.return_value = True
        
        # 模拟MongoDB健康
        mock_mongo_manager.health_check.return_value = True
        
        # 发送请求
        response = self.client.get('/api/health')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['services']['redis']['status'], 'healthy')
        self.assertEqual(data['services']['mongodb']['status'], 'healthy')
    
    @patch('src.api_service.get_task_manager')
    def test_16_health_check_redis_unhealthy(self, mock_get_task_manager):
        """测试Redis不健康时的健康检查"""
        # 模拟任务管理器
        mock_task_manager = Mock()
        mock_get_task_manager.return_value = mock_task_manager
        mock_task_manager.health_check.return_value = False
        
        # 发送请求
        response = self.client.get('/api/health')
        
        # 验证响应
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data['services']['redis']['status'], 'unhealthy')
    
    def test_17_invalid_json_request(self):
        """测试无效JSON请求"""
        # 发送无效JSON
        response = self.client.post('/api/task/submit',
                                  data='invalid json',
                                  content_type='application/json')
        
        # 验证响应（Flask的错误处理会返回500，因为API内部捕获了异常）
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    def test_18_missing_required_fields(self):
        """测试缺少必需字段的请求"""
        # 发送空参数
        response = self.client.post('/api/task/submit',
                                  json={},
                                  content_type='application/json')
        
        # 验证响应
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertFalse(data['success'])


class TestAPIServiceIntegration(unittest.TestCase):
    """API服务集成测试（需要真实Redis连接）"""
    
    @classmethod
    def setUpClass(cls):
        """集成测试初始化"""
        # 创建Flask测试应用
        cls.app = Flask(__name__)
        cls.app.register_blueprint(api_bp)
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        
        # 尝试连接真实Redis
        try:
            from src.task_manager import get_task_manager
            cls.task_manager = get_task_manager({
                'host': 'localhost',
                'port': 6379,
                'db': 15,
                'key_prefix': 'integration_test:',
                'expire_time': 300
            })
            cls.redis_available = cls.task_manager.health_check()
        except Exception as e:
            print(f"Redis不可用，跳过集成测试: {e}")
            cls.redis_available = False
    
    def setUp(self):
        """每个测试前的准备"""
        if not self.redis_available:
            self.skipTest("Redis不可用，跳过集成测试")
        
        self.test_task_id = f"integration_test_{int(time.time())}"
        self.test_params = {
            "topic": "集成测试主题",
            "description": "这是一个集成测试",
            "output_file": f"integration_test_{int(time.time())}.json"
        }
    
    def tearDown(self):
        """每个测试后的清理"""
        if self.redis_available and hasattr(self, 'test_task_id'):
            self.task_manager.delete_task(self.test_task_id)
    
    def test_real_task_lifecycle(self):
        """测试真实的任务生命周期"""
        if not self.redis_available:
            self.skipTest("Redis不可用")
        
        # 创建任务
        self.task_manager.create_task(self.test_task_id, self.test_params)
        
        # 获取任务状态
        response = self.client.get(f'/api/task/{self.test_task_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['task']['id'], self.test_task_id)
        
        # 更新任务状态
        self.task_manager.update_task_status(self.test_task_id, TaskStatus.PROCESSING)
        
        # 再次获取状态
        response = self.client.get(f'/api/task/{self.test_task_id}')
        data = json.loads(response.data)
        self.assertEqual(data['task']['status'], TaskStatus.PROCESSING.value)
        
        # 删除任务
        response = self.client.delete(f'/api/task/{self.test_task_id}')
        self.assertEqual(response.status_code, 200)
        
        # 验证任务已删除
        response = self.client.get(f'/api/task/{self.test_task_id}')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    # 设置测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加单元测试
    suite.addTests(loader.loadTestsFromTestCase(TestAPIService))
    
    # 添加集成测试（可选）
    suite.addTests(loader.loadTestsFromTestCase(TestAPIServiceIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试结果摘要
    print(f"\n{'='*50}")
    print(f"测试完成: 运行 {result.testsRun} 个测试")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"{'='*50}")
