#!/usr/bin/env python3
"""
数据库优化系统测试脚本

用于验证MongoDB集成和数据库优化功能是否正常工作
"""

import sys
import os
import json
import time
import requests
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_database_connection():
    """测试数据库连接"""
    print("🔍 测试数据库连接...")
    
    try:
        from src.database import mongo_manager
        
        if mongo_manager.connect():
            print("✅ 数据库连接成功")
            
            # 测试健康检查
            health = mongo_manager.health_check()
            print(f"✅ 数据库健康状态: {'正常' if health else '异常'}")
            
            # 获取统计信息
            stats = mongo_manager.get_stats()
            print(f"📊 数据库统计: {stats['total_surveys']} 个综述记录")
            
            return True
        else:
            print("❌ 数据库连接失败")
            return False
            
    except ImportError:
        print("❌ 数据库模块不可用，可能缺少pymongo")
        return False
    except Exception as e:
        print(f"❌ 数据库连接异常: {str(e)}")
        return False


def test_api_endpoints():
    """测试API端点"""
    print("\n🌐 测试API端点...")
    
    base_url = "http://localhost:5000"
    
    endpoints = [
        ("/api/database/health", "数据库健康检查"),
        ("/api/database/stats", "数据库统计信息"),
        ("/api/global_pipeline_status", "全局Pipeline状态"),
        ("/api/tasks", "任务列表"),
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {description}: 正常")
            else:
                print(f"⚠️ {description}: HTTP {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ {description}: 连接失败 (服务器未启动?)")
        except Exception as e:
            print(f"❌ {description}: {str(e)}")


def test_complete_workflow():
    """测试完整工作流程"""
    print("\n🚀 测试完整工作流程...")
    
    base_url = "http://localhost:5000"
    
    # 测试数据
    test_data = {
        "topic": "测试主题",
        "description": "这是一个测试主题的描述",
        "top_n": 10
    }
    
    try:
        # 启动任务
        print("📝 提交测试任务...")
        response = requests.post(
            f"{base_url}/api/task/submit",
            json=test_data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result['task_id']
            print(f"✅ 任务已提交: {task_id}")
            
            # 监控任务状态
            print("⏳ 监控任务状态...")
            for i in range(10):  # 最多检查10次
                time.sleep(5)
                
                status_response = requests.get(
                    f"{base_url}/api/task/{task_id}",
                    timeout=5
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    task_status = status_data['task']['status']
                    print(f"📊 任务状态: {task_status}")
                    
                    if task_status in ['completed', 'failed']:
                        break
                else:
                    print("❌ 无法获取任务状态")
                    break
            
            return task_id
        else:
            print(f"❌ 任务提交失败: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 工作流程测试失败: {str(e)}")
        return None


def test_database_operations():
    """测试数据库操作"""
    print("\n💾 测试数据库操作...")
    
    try:
        from src.database import mongo_manager
        
        # 测试保存数据
        test_task_id = f"test_{int(time.time())}"
        test_survey_data = {
            "title": "测试综述",
            "content": "这是测试内容",
            "created_at": datetime.now().isoformat()
        }
        
        print("💿 测试保存数据...")
        save_result = mongo_manager.save_survey(test_task_id, test_survey_data)
        if save_result:
            print("✅ 数据保存成功")
        else:
            print("❌ 数据保存失败")
            return False
        
        # 测试读取数据
        print("📖 测试读取数据...")
        retrieved_data = mongo_manager.get_survey(test_task_id)
        if retrieved_data:
            print("✅ 数据读取成功")
            print(f"📄 标题: {retrieved_data.get('title')}")
        else:
            print("❌ 数据读取失败")
            return False
        
        # 测试删除数据
        print("🗑️ 测试删除数据...")
        delete_result = mongo_manager.delete_survey(test_task_id)
        if delete_result:
            print("✅ 数据删除成功")
        else:
            print("❌ 数据删除失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库操作测试失败: {str(e)}")
        return False


def main():
    """主测试函数"""
    print("🧪 LLMxMapReduce 数据库优化系统测试")
    print("=" * 50)
    
    # 测试数据库连接
    db_ok = test_database_connection()
    
    # 测试API端点
    test_api_endpoints()
    
    # 如果数据库可用，测试数据库操作
    if db_ok:
        test_database_operations()
    
    # 测试完整工作流程（可选）
    print("\n❓ 是否要测试完整工作流程? (需要服务器运行) [y/N]: ", end="")
    user_input = input().strip().lower()
    
    if user_input in ['y', 'yes']:
        task_id = test_complete_workflow()
        if task_id:
            print(f"\n📋 测试任务ID: {task_id}")
            print("💡 您可以通过以下API查看任务状态:")
            print(f"   curl http://localhost:5000/api/task/{task_id}")
    
    print("\n🎉 测试完成!")


if __name__ == "__main__":
    main() 