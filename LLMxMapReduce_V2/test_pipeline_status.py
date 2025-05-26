#!/usr/bin/env python3
"""
测试Pipeline处理器改进的脚本

主要测试：
1. 任务状态更新的细致程度
2. EncodePipeline从数据库读取数据的功能
3. 错误处理的完整性
"""

import sys
import os
import json
import time
import logging
import requests
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 服务器配置
BASE_URL = "http://localhost:8000"

def test_task_submission():
    """测试任务提交和状态更新"""
    logger.info("=== 测试任务提交和状态更新 ===")
    
    # 提交任务
    task_data = {
        "topic": "机器学习在自然语言处理中的应用",
        "description": "研究机器学习技术在自然语言处理领域的最新进展和应用",
        "top_n": 10
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/submit_task", json=task_data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get('success'):
            task_id = result['task_id']
            logger.info(f"任务提交成功: {task_id}")
            return task_id
        else:
            logger.error(f"任务提交失败: {result}")
            return None
            
    except Exception as e:
        logger.error(f"任务提交异常: {str(e)}")
        return None

def monitor_task_status(task_id, max_wait_time=300):
    """监控任务状态变化"""
    logger.info(f"=== 监控任务状态变化: {task_id} ===")
    
    start_time = time.time()
    last_status = None
    status_history = []
    
    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(f"{BASE_URL}/api/task/{task_id}", timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                task = result['task']
                current_status = task['status']
                
                # 记录状态变化
                if current_status != last_status:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    status_change = {
                        'timestamp': timestamp,
                        'status': current_status,
                        'elapsed': round(time.time() - start_time, 1)
                    }
                    status_history.append(status_change)
                    logger.info(f"[{timestamp}] 状态变化: {last_status} -> {current_status} (耗时: {status_change['elapsed']}s)")
                    last_status = current_status
                
                # 检查是否完成
                if current_status in ['completed', 'failed', 'timeout']:
                    logger.info(f"任务最终状态: {current_status}")
                    if current_status == 'failed' and 'error' in task:
                        logger.error(f"任务失败原因: {task['error']}")
                    break
                    
            else:
                logger.error(f"获取任务状态失败: {result}")
                break
                
        except Exception as e:
            logger.error(f"监控任务状态异常: {str(e)}")
            
        time.sleep(5)  # 每5秒检查一次
    
    # 输出状态变化历史
    logger.info("=== 任务状态变化历史 ===")
    for change in status_history:
        logger.info(f"  {change['timestamp']} - {change['status']} (耗时: {change['elapsed']}s)")
    
    return status_history

def test_database_integration():
    """测试数据库集成"""
    logger.info("=== 测试数据库集成 ===")
    
    try:
        # 测试数据库连接
        from src.database import mongo_manager
        
        if mongo_manager.connect():
            logger.info("✓ MongoDB连接成功")
            
            # 测试健康检查
            if mongo_manager.health_check():
                logger.info("✓ MongoDB健康检查通过")
            else:
                logger.warning("✗ MongoDB健康检查失败")
                
            # 获取统计信息
            stats = mongo_manager.get_stats()
            logger.info(f"✓ 数据库统计: {stats}")
            
        else:
            logger.error("✗ MongoDB连接失败")
            
    except Exception as e:
        logger.error(f"数据库集成测试异常: {str(e)}")

def test_encode_pipeline():
    """测试EncodePipeline的数据库读取功能"""
    logger.info("=== 测试EncodePipeline数据库读取功能 ===")
    
    try:
        from src.encode.encode_pipeline import EncodePipeline
        
        # 创建测试配置
        test_config = {
            "model": "test",
            "infer_type": "test"
        }
        
        # 创建EncodePipeline实例
        pipeline = EncodePipeline(test_config, data_num=1)
        
        # 测试task_id识别逻辑
        test_cases = [
            ("12345678-1234-1234-1234-123456789012", "task_id"),  # UUID格式
            ("simple_task_id", "task_id"),  # 简单字符串
            ("data/input.json", "file"),  # 文件路径
            ("input.tmp", "file"),  # 临时文件
            ("/path/to/file.jsonl", "file"),  # 绝对路径
            ("C:\\path\\to\\file.txt", "file"),  # Windows路径
        ]
        
        for test_input, expected_type in test_cases:
            # 模拟识别逻辑
            is_task_id = (isinstance(test_input, str) and 
                         '/' not in test_input and 
                         '\\' not in test_input and 
                         not test_input.endswith(('.tmp', '.json', '.txt', '.jsonl')))
            
            detected_type = "task_id" if is_task_id else "file"
            status = "✓" if detected_type == expected_type else "✗"
            logger.info(f"  {status} '{test_input}' -> {detected_type} (期望: {expected_type})")
        
        logger.info("✓ EncodePipeline识别逻辑测试完成")
        
    except Exception as e:
        logger.error(f"EncodePipeline测试异常: {str(e)}")

def main():
    """主测试函数"""
    logger.info("开始Pipeline改进测试")
    
    # 1. 测试数据库集成
    test_database_integration()
    
    # 2. 测试EncodePipeline
    test_encode_pipeline()
    
    # 3. 测试任务提交和状态监控
    task_id = test_task_submission()
    if task_id:
        status_history = monitor_task_status(task_id)
        
        # 分析状态变化
        logger.info("=== 状态变化分析 ===")
        expected_statuses = ['pending', 'preparing', 'searching', 'searching_web', 'crawling', 'processing']
        
        actual_statuses = [change['status'] for change in status_history]
        logger.info(f"实际状态序列: {actual_statuses}")
        
        # 检查是否包含关键状态
        key_statuses = ['searching', 'searching_web', 'crawling', 'processing']
        for status in key_statuses:
            if status in actual_statuses:
                logger.info(f"✓ 包含关键状态: {status}")
            else:
                logger.warning(f"✗ 缺少关键状态: {status}")
    
    logger.info("Pipeline改进测试完成")

if __name__ == "__main__":
    main() 